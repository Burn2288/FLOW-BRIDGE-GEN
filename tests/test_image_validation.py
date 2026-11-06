"""Provider image integrity and rejection before Telegram delivery or persistence."""

import asyncio
import base64
from dataclasses import replace
from io import BytesIO
import socket
import struct
from unittest.mock import AsyncMock
import zlib

import httpx
from PIL import Image
import pytest

from elevenbot import interaction
from elevenbot.core import Rejected
from elevenbot.discovery import SnapshotStore, snapshot
from elevenbot.telegram import MENU, TelegramApp
from test_ui import Bot, event


OPERATION = "images.generate"
MODEL = {
    "id": "nano-banana-2",
    "title": "Image fixture",
    "provider": "clodex",
    "availability": "key_available",
    "operations": [OPERATION],
}
PNG_SIGNATURE_ONLY = bytes.fromhex("89504e470d0a1a0a")
JPEG_MARKERS_ONLY = bytes.fromhex("ffd8ffffd9")


def encoded_image(format, size=(32, 32), mode="RGB", **options):
    buffer = BytesIO()
    with Image.new(mode, size) as image:
        image.save(buffer, format=format, **options)
    return buffer.getvalue()


@pytest.fixture
def provider_stub(monkeypatch):
    def make(image, source):
        requests = []

        async def resolve(host, port, *, type):
            assert (host, port, type) == ("fixture.invalid", 443, socket.SOCK_STREAM)
            return [(socket.AF_INET, type, 0, "", ("93.184.216.34", 443))]

        def respond(request):
            requests.append(request)
            if request.method == "POST":
                assert request.url.path == "/v1/images/generations"
                if source == "url":
                    result = {"url": "https://fixture.invalid/image"}
                else:
                    result = {"b64_json": base64.b64encode(image).decode("ascii")}
                return httpx.Response(200, json={"data": [result]})
            assert request.method == "GET"
            assert request.url.host == "93.184.216.34"
            assert request.headers["Host"] == "fixture.invalid"
            assert "Authorization" not in request.headers
            return httpx.Response(200, content=image)

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
        return httpx.AsyncClient(transport=httpx.MockTransport(respond)), requests

    return make


@pytest.mark.parametrize("source", ["b64_json", "url"])
@pytest.mark.parametrize(
    ("format", "mode", "options", "filename"),
    [
        ("PNG", "RGBA", {}, "result.png"),
        ("JPEG", "RGB", {"progressive": True}, "result.jpg"),
        ("JPEG", "CMYK", {}, "result.jpg"),
    ],
)
async def test_valid_provider_image_keeps_original_bytes(provider_stub, source, format, mode, options, filename):
    original = encoded_image(format, mode=mode, **options)
    client, requests = provider_stub(original, source)
    async with client:
        result = await interaction.execute(OPERATION, MODEL, "fixture", [], mode="live", key="test", client=client)
    assert result.image == original
    assert result.filename == filename
    assert [request.method for request in requests] == (["POST", "GET"] if source == "url" else ["POST"])


@pytest.mark.parametrize("source", ["b64_json", "url"])
@pytest.mark.parametrize("fake_image", [PNG_SIGNATURE_ONLY, JPEG_MARKERS_ONLY], ids=["png-signature", "jpeg-markers"])
async def test_rejects_signature_only_provider_response(provider_stub, source, fake_image):
    client, requests = provider_stub(fake_image, source)
    async with client:
        with pytest.raises(Rejected):
            await interaction.execute(OPERATION, MODEL, "fixture", [], mode="live", key="test", client=client)
    assert [request.method for request in requests] == (["POST", "GET"] if source == "url" else ["POST"])


def test_rejects_png_crc_corruption_and_truncation():
    png = bytearray(encoded_image("PNG"))
    png[png.index(b"IDAT") + 4] ^= 1
    with pytest.raises(Rejected):
        interaction.image_result(bytes(png))
    with pytest.raises(Rejected):
        interaction.image_result(encoded_image("PNG")[:-4])


def test_rejects_png_with_missing_zlib_trailer_and_valid_chunk_crc():
    png = encoded_image("PNG")
    start = png.index(b"IDAT")
    length = struct.unpack_from(">I", png, start - 4)[0]
    incomplete = png[start:start + length]
    rebuilt = (
        png[:start - 4] + struct.pack(">I", length - 4) + incomplete
        + struct.pack(">I", zlib.crc32(incomplete)) + png[start + length + 8:]
    )
    with pytest.raises(Rejected):
        interaction.image_result(rebuilt)


def test_png_frames_share_the_pixel_budget(monkeypatch):
    with Image.new("RGBA", (16, 16), "red") as first, Image.new("RGBA", (16, 16), "blue") as second:
        buffer = BytesIO()
        first.save(buffer, format="PNG", save_all=True, append_images=[second])
    original = buffer.getvalue()
    assert interaction.image_result(original).image == original
    monkeypatch.setattr(interaction, "IMAGE_MAX_PIXELS", 16 * 16)
    with pytest.raises(Rejected):
        interaction.image_result(original)


def test_rejects_jpeg_with_missing_scan_data_even_with_end_marker():
    jpeg = encoded_image("JPEG")
    scan = jpeg.index(b"\xff\xda")
    scan_length = int.from_bytes(jpeg[scan + 2:scan + 4], "big")
    corrupt = jpeg[:scan + 2 + scan_length] + jpeg[-2:]
    with pytest.raises(Rejected):
        interaction.image_result(corrupt)


@pytest.mark.parametrize("format", ["PNG", "JPEG"])
@pytest.mark.parametrize("limit", ["IMAGE_MAX_SIDE", "IMAGE_MAX_PIXELS"])
def test_rejects_dimensions_before_pixel_decode(monkeypatch, format, limit):
    image = encoded_image(format)
    monkeypatch.setattr(interaction, limit, 16)
    decode = "decode_jpeg" if format == "JPEG" else "load"
    target = interaction if format == "JPEG" else Image.Image

    def unexpected_decode(*args, **kwargs):
        pytest.fail("Pixel decoder must not run when dimensions exceed the budget")

    monkeypatch.setattr(target, decode, unexpected_decode)
    with pytest.raises(Rejected):
        interaction.image_result(image)


@pytest.mark.parametrize("source", ["b64_json", "url"])
async def test_corrupt_provider_image_is_not_saved_sent_or_retried(env, tmp_path, monkeypatch, provider_stub, source):
    pool, base_config, service, user = env
    catalogue = tmp_path / "catalogue.json"
    SnapshotStore(catalogue).write(snapshot([MODEL]))
    config = replace(
        base_config,
        access_mode="private",
        admin_ids=(100,),
        catalogue_path=str(catalogue),
        interaction_mode="live",
        interaction_pairs=(f"{OPERATION}:{MODEL['id']}",),
        clodex_key="fixture-only",
    )
    bot = Bot()
    bot.send_photo = AsyncMock()
    bot.send_document = AsyncMock()
    app = TelegramApp(pool, config, bot)
    await service.aggregate_context(user, {"interaction": OPERATION, "model_id": MODEL["id"], "history": []})
    execute = interaction.execute
    client, requests = provider_stub(PNG_SIGNATURE_ONLY if source == "b64_json" else JPEG_MARKERS_ONLY, source)

    async def execute_against_stub(*args, **kwargs):
        return await execute(*args, **kwargs, client=client)

    monkeypatch.setattr(interaction, "execute", execute_against_stub)
    async with client:
        prompt = event("Draw a fixture")
        await app.handle(prompt)
        assert "Не удалось создать изображение." in bot.sent[-1][0]
        await app.handle(prompt)
        await app.handle(event(MENU[1]).model_copy(update={"update_id": 2}))

    assert [request.method for request in requests] == (["POST", "GET"] if source == "url" else ["POST"])
    assert await pool.fetchval("SELECT count(*) FROM interaction_attempts") == 1
    assert await pool.fetchval("SELECT count(*) FROM image_works") == 0
    assert "Работ пока нет." in bot.sent[-1][0]
    bot.send_photo.assert_not_called()
    bot.send_document.assert_not_called()
