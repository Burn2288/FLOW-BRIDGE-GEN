"""A persisted image survives a failed Telegram upload and a gateway restart."""

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiohttp import web

from elevenbot.aggregate import make_snapshot
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import STORE_SECTIONS, WELCOME_TEXT


ROOT = Path(__file__).resolve().parents[1]
BOT_WITH_PROVIDER_COUNTER = """
import asyncio
import os
from pathlib import Path

from elevenbot import interaction
from elevenbot.__main__ import main

mock_execute = interaction.execute

async def count_generation(*args, **kwargs):
    assert kwargs["mode"] == "mock"
    with Path(os.environ["PROVIDER_CALLS"]).open("a", encoding="utf-8") as log:
        log.write("generate\\n")
    return await mock_execute(*args, **kwargs)

interaction.execute = count_generation
asyncio.run(main())
"""


async def test_saved_image_reopens_after_send_photo_failure_and_restart(env, tmp_path):
    pool, _, _, user_id = env
    schema = await pool.fetchval("SELECT current_schema()")
    parts = urlsplit(os.environ["TEST_DATABASE_URL"])
    dsn = urlunsplit(parts._replace(query=urlencode([*parse_qsl(parts.query), ("search_path", schema)])))
    catalogue = tmp_path / "catalogue.json"
    model = {
        "id": "image-fixture",
        "title": "Image fixture",
        "provider": "clodex",
        "availability": "key_available",
        "operations": ["images.generate"],
    }
    SnapshotStore(catalogue).write(make_snapshot([model],[],[{'provider':'clodex','scope':'key_available'}]))
    provider_calls = tmp_path / "provider-calls.txt"
    updates = []
    screens = []
    uploads = []
    external_user = {"id": 100, "is_bot": False, "first_name": "Fixture"}
    chat = {"id": 100, "type": "private"}

    async def telegram(request):
        method = request.match_info["method"].lower()
        form = await request.post()
        if method == "getupdates":
            offset = int(form.get("offset", "0"))
            pending = [update for update in updates if update["update_id"] >= offset]
            if not pending:
                await asyncio.sleep(0.1)
            return web.json_response({"ok": True, "result": pending})
        if method in ("answercallbackquery", "deletemessage"):
            return web.json_response({"ok": True, "result": True})
        if method == "sendphoto" and form.get("caption") != WELCOME_TEXT:
            image = form[form["photo"].removeprefix("attach://")].file.read()
            uploads.append((int(form["chat_id"]), image))
            if len(uploads) == 1:
                persisted = await pool.fetchval("SELECT image FROM image_works WHERE user_id=$1", user_id)
                assert persisted == image
                return web.json_response(
                    {"ok": False, "error_code": 400, "description": "Injected sendPhoto failure"},
                    status=400,
                )
        else:
            assert method in ("sendmessage", "editmessagetext", "editmessagecaption", "sendphoto", "sendanimation"), method
        message_id = int(form["message_id"]) if method in ("editmessagetext","editmessagecaption") else 1000 + len(screens)
        if method != "sendphoto":
            screens.append((message_id, json.loads(form.get("reply_markup", "{}"))))
        return web.json_response({
            "ok": True,
            "result": {"message_id": message_id, "date": int(time.time()), "chat": chat},
        })

    app = web.Application(client_max_size=3*1024**2)
    app.router.add_post("/bot{token}/{method}", telegram)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    await pool.execute("INSERT INTO approved_models VALUES('clodex','image-fixture','images.generate','Image fixture')")
    config = os.environ | {
        "DATABASE_URL": dsn,
        "PROVIDER_MODE": "mock",
        "ACCESS_MODE": "public",
        "ADMIN_TELEGRAM_IDS": "",
        "CLODEX_INTERACTION_MODE": "mock",
        "CLODEX_SPEECH_PILOT": "false",
        "PAYMENTS_ENABLED": "false",
        "CATALOGUE_ENABLED": "false",
        "CATALOGUE_PATH": str(catalogue),
        "PUBLIC_CATALOGUE_MODELS": "image:image-fixture",
        "TELEGRAM_BOT_TOKEN": "123456:" + "fixture_" * 5,
        "TELEGRAM_API_BASE": f"http://127.0.0.1:{port}",
        "ALLOW_LOCAL_TELEGRAM_STUB": "true",
        "PROVIDER_CALLS": str(provider_calls),
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONUNBUFFERED": "1",
    }

    @asynccontextmanager
    async def gateway(label):
        log = tmp_path / f"{label}.log"
        with log.open("wb") as output:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-c", BOT_WITH_PROVIDER_COUNTER, "bot",
                env=config, stdout=output, stderr=output,
            )
            try:
                yield process
            except Exception:
                print(log.read_text(encoding="utf-8", errors="replace"))
                raise
            finally:
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), 5)
                    except TimeoutError:
                        process.kill()
                        await process.wait()

    update_id = 0

    async def send_update(process, *, text=None, button=None):
        nonlocal update_id
        update_id += 1
        message = {"message_id": update_id, "date": int(time.time()), "chat": chat, "from": external_user}
        update = {"update_id": update_id}
        if button is None:
            update["message"] = message | {"text": text}
        else:
            screen_id, markup = screens[-1]
            callbacks = [
                key["callback_data"] for row in markup["inline_keyboard"] for key in row
                if key["text"].startswith(button)
            ]
            assert len(callbacks) == 1, f"Expected one visible button starting with {button!r}"
            update["callback_query"] = {
                "id": str(update_id), "chat_instance": "fixture", "from": external_user,
                "data": callbacks[0], "message": message | {
                    "message_id": screen_id, "from": {"id": 123456, "is_bot": True, "first_name": "Bot"},
                },
            }
        updates.append(update)
        async with asyncio.timeout(15):
            while not await pool.fetchval("SELECT done FROM inbox WHERE update_id=$1", update_id):
                assert process.returncode is None, "Gateway stopped before processing the update"
                await asyncio.sleep(0.05)

    try:
        async with gateway("before-restart") as first:
            await send_update(first, text="/start")
            await send_update(first, text="/menu")
            await send_update(first, button="Агрегатор 1")
            await send_update(first, button="🎆 Генерировать изображение")
            await send_update(first, button="Image fixture")
            await send_update(first, button=STORE_SECTIONS["image"][0])
            await send_update(first, text="Draw a fixture")
            before = await pool.fetchrow("SELECT id, image FROM image_works WHERE user_id=$1", user_id)
            assert before and before["image"] == MOCK_IMAGE
            assert uploads == [(100, before["image"])]
            assert "result_display_failed" in (tmp_path / "before-restart.log").read_text(encoding="utf-8")
            digest_before = hashlib.sha256(before["image"]).hexdigest()

        async with gateway("after-restart") as second:
            assert second.pid != first.pid
            await send_update(second, text="/menu")
            await send_update(second, button="📁 Мои работы")
            await send_update(second, button="Открыть работу №")
            assert len(uploads) == 2
            recipient, recovered = uploads[1]
            assert recipient == external_user["id"]
            digest_after = hashlib.sha256(recovered).hexdigest()
            assert digest_after == digest_before
            assert await pool.fetchrow("SELECT id, image FROM image_works WHERE user_id=$1", user_id) == before
            calls = provider_calls.read_text(encoding="utf-8").splitlines()
            assert calls == ["generate"]
            print(f"before_sha256={digest_before} after_sha256={digest_after} provider_calls={len(calls)}")
    finally:
        await runner.cleanup()
