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
    "id": "flux-schnell",
    "title": "Image fixture",
    "provider": "clodex",
    "availability": "key_available",
    "operations": [OPERATION],
    "protocols": ["image-generation"],
}
PNG_SIGNATURE_ONLY = bytes.fromhex("89504e470d0a1a0a")
JPEG_MARKERS_ONLY = bytes.fromhex("ffd8ffffd9")


def encoded_image(format, size=(32, 32), mode="RGB", **options):
    buffer = BytesIO()
    with Image.new(mode, size) as image:
        image.save(buffer, format=format, **options)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("url", "dns", "reason"),
    [
        ("http://fixture.invalid/image", None, "url_scheme"),
        ("https:/image", None, "url_host_missing"),
        ("https://user:password@fixture.invalid/image", None, "url_userinfo"),
        ("https://fixture.invalid:8443/image", None, "url_port"),
        ("https://fixture.invalid/image", [], "dns_no_addresses"),
        ("https://fixture.invalid/image", ["93.184.216.34", "127.0.0.1"], "dns_non_public"),
        ("https://fixture.invalid/image", ["not-an-ip"], "dns_invalid_address"),
        ("https://fixture.invalid/image", socket.gaierror("private DNS details"), "dns_lookup"),
    ],
)
async def test_image_download_diagnostics_do_not_log_url(monkeypatch, capsys, url, dns, reason):
    async def resolve(*args, **kwargs):
        assert dns is not None, "URL must be rejected before DNS"
        if isinstance(dns, OSError):
            raise dns
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 443)) for ip in dns]

    def unexpected_request(request):
        pytest.fail("Rejected URL must not reach the HTTP transport")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)) as client:
        with pytest.raises(Rejected):
            await interaction.download_image(client, url + "?signature=fixture-secret", request_id=1)
    output = capsys.readouterr().out
    assert f'"reason": "{reason}"' in output
    assert all(value not in output for value in ("fixture.invalid", "fixture-secret", "password", "private DNS details"))


def png_chunk(kind, data):
    chunk = kind + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk))


def png_header(width, height, bit_depth, color_type, interlace=0):
    return PNG_SIGNATURE_ONLY + png_chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, interlace),
    )


def test_rejects_rgb_png_with_extra_scanline_byte():
    # One filter byte plus one RGB pixel uses four bytes. Only the length is wrong.
    png = (
        png_header(1, 1, 8, 2)
        + png_chunk(b"IDAT", zlib.compress(bytes(5)))
        + png_chunk(b"IEND", b"")
    )
    with pytest.raises(Rejected):
        interaction.image_result(png)


@pytest.mark.parametrize(("size", "data_length"), [(1, 2), (9, 42)])
def test_adam7_png_uses_packed_scanlines_of_nonempty_passes(size, data_length):
    header = png_header(size, size, 1, 0, interlace=1)
    end = png_chunk(b"IEND", b"")
    compressed = zlib.compress(bytes(data_length))
    original = header + png_chunk(b"IDAT", compressed[:-2]) + png_chunk(b"IDAT", compressed[-2:]) + end
    assert interaction.image_result(original).image == original
    with pytest.raises(Rejected):
        interaction.image_result(header + png_chunk(b"IDAT", zlib.compress(bytes(data_length + 1))) + end)


@pytest.mark.parametrize("default_image", [False, True])
def test_apng_checks_each_frame_at_its_own_dimensions(default_image):
    def frame_control(sequence, width, height, x=0, y=0):
        return png_chunk(b"fcTL", struct.pack(">IIIIIHHBB", sequence, width, height, x, y, 1, 10, 0, 0))

    # Three RGB pixels plus a filter byte in each of the two canvas rows.
    start = png_header(3, 2, 8, 2) + png_chunk(b"acTL", struct.pack(">II", 1 if default_image else 2, 0))
    if not default_image:
        start += frame_control(0, 3, 2)
    start += png_chunk(b"IDAT", zlib.compress(bytes(20)))
    sequence = 0 if default_image else 1
    start += frame_control(sequence, 1, 1, x=1, y=1)
    frame_sequence = struct.pack(">I", sequence + 1)
    end = png_chunk(b"IEND", b"")
    original = start + png_chunk(b"fdAT", frame_sequence + zlib.compress(bytes(4))) + end
    assert interaction.image_result(original).image == original
    for wrong_length in (3, 5):
        corrupt = start + png_chunk(b"fdAT", frame_sequence + zlib.compress(bytes(wrong_length))) + end
        with pytest.raises(Rejected):
            interaction.image_result(corrupt)


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
@pytest.mark.parametrize("format", ["PNG", "JPEG"])
async def test_corrupt_provider_image_keeps_bounded_original_bytes(provider_stub, source, format):
    original = encoded_image(format)
    if format == "PNG":
        damaged = bytearray(original)
        damaged[damaged.index(b"IDAT") + 4] ^= 1  # Break the IDAT CRC without changing its header.
        damaged = bytes(damaged)
    else:
        scan = original.index(b"\xff\xda")
        scan_length = int.from_bytes(original[scan + 2:scan + 4], "big")
        damaged = original[:scan + 2 + scan_length] + original[-2:]  # Keep headers, omit scan data.
    client, requests = provider_stub(damaged, source)
    async with client:
        result = await interaction.execute(OPERATION, MODEL, "fixture", [], mode="live", key="test", client=client)
    assert result.image == damaged
    assert result.filename == ("result.png" if format == "PNG" else "result.jpg")
    assert [request.method for request in requests] == (["POST", "GET"] if source == "url" else ["POST"])


def test_provider_image_header_still_obeys_size_and_dimension_limits(monkeypatch):
    original = encoded_image("PNG")
    monkeypatch.setattr(interaction, "IMAGE_MAX_SIDE", 16)
    with pytest.raises(Rejected):
        interaction.provider_image_result(original)
    with pytest.raises(Rejected):
        interaction.provider_image_result(b"\x89PNG\r\n\x1a\n")


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
async def test_corrupt_provider_image_is_saved_delivered_and_reopened_without_regeneration(
    funded_env, tmp_path, monkeypatch, provider_stub, source, manual_tariff,
):
    from aiohttp.test_utils import TestClient, TestServer
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendPhoto
    from miniapp.backend.web import create_app
    from miniapp.tests.test_miniapp import signed

    pool, base_config, service, user = funded_env
    catalogue = tmp_path / "catalogue.json"
    SnapshotStore(catalogue).write(snapshot([MODEL]))
    config = replace(
        base_config,
        access_mode="private",
        admin_ids=(100,),
        pilot_user_ids=(101,),
        catalogue_path=str(catalogue),
        interaction_mode="live",
        interaction_pairs=(f"{OPERATION}:{MODEL['id']}",),
        clodex_key="fixture-only",
        interaction_limit=1,
        token="fixture",
    )
    bot = Bot()
    bot.send_photo = AsyncMock(side_effect=TelegramBadRequest(
        method=SendPhoto(chat_id=100, photo="fixture"), message="PHOTO_INVALID_DIMENSIONS",
    ))
    bot.send_document = AsyncMock()
    app = TelegramApp(pool, config, bot)
    await manual_tariff(app,user,MODEL["id"],OPERATION,{"n":1})
    await service.aggregate_context(user, {"interaction": OPERATION, "model_id": MODEL["id"], "history": []})
    execute = interaction.execute
    damaged = bytearray(encoded_image("PNG"))
    damaged[damaged.index(b"IDAT") + 4] ^= 1
    damaged = bytes(damaged)
    client, requests = provider_stub(damaged, source)

    async def execute_against_stub(*args, **kwargs):
        return await execute(*args, **kwargs, client=client)

    monkeypatch.setattr(interaction, "execute", execute_against_stub)
    async with client:
        prompt = event("Draw a fixture")
        await app.handle(prompt)
        assert not requests
        confirm=bot.sent[-1][1].inline_keyboard[0][0].callback_data
        await app.handle(event(callback=confirm).model_copy(update={"update_id": 2}))
        assert bot.send_photo.await_count == 1 and bot.send_document.await_count == 1
        assert bot.send_document.await_args.args[1].data == damaged
        work = await pool.fetchrow("SELECT id,image,filename,prompt FROM image_works WHERE user_id=$1", user)
        assert work is not None and work["image"] == damaged and work["filename"] == "result.png"
        assert work["prompt"] == "Draw a fixture"
        ledger = [tuple(row) for row in await pool.fetch(
            "SELECT event_key,kind,da,dr FROM ledger WHERE user_id=$1 ORDER BY event_key", user,
        )]
        await app.handle(event(callback=confirm).model_copy(update={"update_id": 3}))
        assert [tuple(row) for row in await pool.fetch(
            "SELECT event_key,kind,da,dr FROM ledger WHERE user_id=$1 ORDER BY event_key", user,
        )] == ledger
        reopened = await app.svc.image_work(user, work["id"])
        assert reopened["image"] == damaged
        restarted_bot = Bot()
        restarted_bot.send_photo = AsyncMock(side_effect=TelegramBadRequest(
            method=SendPhoto(chat_id=100, photo="fixture"), message="PHOTO_INVALID_DIMENSIONS",
        ))
        restarted_bot.send_document = AsyncMock()
        await TelegramApp(pool, config, restarted_bot).open_work(user, 100, "image", str(work["id"]))
        assert restarted_bot.send_document.await_count == 1
        assert restarted_bot.send_document.await_args.args[1].data == damaged
        other = await service.identity(101)
        await service.accept(other)
        with pytest.raises(Rejected):
            await app.svc.image_work(other, work["id"])
        async with TestClient(TestServer(create_app(pool, config))) as miniapp:
            login = await miniapp.post("/api/v1/session", json={"initData": signed("fixture", 100)})
            assert login.status == 200
            owner_headers = {"Authorization": "Bearer " + (await login.json())["token"]}
            file_response = await miniapp.get(
                f"/api/v1/works/image/{work['id']}", headers=owner_headers,
            )
            assert file_response.status == 200 and await file_response.read() == damaged
            assert file_response.headers["Content-Disposition"].endswith('filename="darkflow.png"')
            foreign_login = await miniapp.post("/api/v1/session", json={"initData": signed("fixture", 101)})
            assert foreign_login.status == 200
            foreign_headers = {"Authorization": "Bearer " + (await foreign_login.json())["token"]}
            assert (await miniapp.get(
                f"/api/v1/works/image/{work['id']}", headers=foreign_headers,
            )).status == 404

    assert [request.method for request in requests] == (["POST", "GET"] if source == "url" else ["POST"])
    assert await pool.fetchval("SELECT count(*) FROM interaction_attempts") == 1
    assert await pool.fetchval("SELECT count(*) FROM image_works") == 1
    assert bot.send_photo.await_count == 2 and bot.send_document.await_count == 2
