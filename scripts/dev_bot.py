"""Start the dev gateway against a loopback Telegram smoke fixture."""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

from aiohttp import web


def fixture_environment():
    # Only the private fixture database may be migrated by this launcher.
    from urllib.parse import urlsplit

    dsn = os.environ.get("DATABASE_URL", "")
    db = urlsplit(dsn)
    if (db.scheme != "postgresql" or db.hostname != "127.0.0.1"
            or db.username != "postgres" or db.password != "isolated-test-only"
            or db.path != "/flowbridge_dev" or db.query or db.fragment):
        raise SystemExit("DEV requires its dedicated loopback flowbridge_dev database")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "AUDIO_STORAGE_DIR")
           if key in os.environ}
    return env | {
        "DATABASE_URL": dsn,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "PYTHONUNBUFFERED": "1",
        "PROVIDER_MODE": "mock",
        "CLODEX_INTERACTION_MODE": "mock",
        "GENERATION_ENABLED": "true",
        "PAYMENTS_ENABLED": "false",
        "TELEGRAM_BOT_TOKEN": "123456:" + "fixture_" * 5,
        "TELEGRAM_API_BASE": "http://127.0.0.1:8081",
        "ALLOW_LOCAL_TELEGRAM_STUB": "true",
    }


async def main():
    env = fixture_environment()
    args = sys.argv[1:]
    if args in (["worker"], ["miniapp"]):
        os.execve(sys.executable, [sys.executable, "-m", "elevenbot", args[0]], env)
    if args:
        raise SystemExit("usage: dev_bot.py [worker|miniapp]")
    # Drive the same Telegram conversation as the local process acceptance test.
    steps = ["/start", None, "🎙 Создать озвучку", "DEV fixture", "voice:0", "speed:1.0", None]
    actor = {"id": 100, "is_bot": False, "first_name": "Fixture"}
    chat = {"id": 100, "type": "private"}
    confirm = None
    message_id = 100

    async def telegram(request):
        nonlocal confirm, message_id
        method = request.match_info["method"].lower()
        form = await request.post()
        if method == "getupdates":
            number = max(1, int(form.get("offset", "0")))
            if number > len(steps) or (number == 2 and not steps[1]) or (number == len(steps) and not confirm):
                await asyncio.sleep(0.2)
                return web.json_response({"ok": True, "result": []})
            value = steps[number - 1] or confirm
            msg = {"message_id": number, "date": int(time.time()), "chat": chat, "from": actor}
            update = {"update_id": number}
            if number in (2, 5, 6, 7):
                update["callback_query"] = {"id": str(number), "from": actor,
                    "chat_instance": "fixture", "message": msg, "data": value}
            else:
                update["message"] = msg | {"text": value}
            return web.json_response({"ok": True, "result": [update]})
        if method in ("deletemessage", "answercallbackquery", "setmycommands", "setchatmenubutton"):
            return web.json_response({"ok": True, "result": True})
        if method in ("sendmessage", "sendphoto", "sendaudio", "sendanimation", "senddocument",
                      "editmessagetext", "editmessagecaption"):
            for row in json.loads(form.get("reply_markup", "{}")).get("inline_keyboard", []):
                for button in row:
                    if button["text"] == "Принять":
                        steps[1] = button["callback_data"]
                    if button.get("callback_data", "").startswith("confirm:"):
                        confirm = button["callback_data"]
            if method == "sendaudio":
                print("telegram_stub_delivery=audio", flush=True)
            if method == "sendmessage":
                print("telegram_stub_smoke=ok", flush=True)
            message_id += 1
            return web.json_response({"ok": True, "result": {"message_id": message_id,
                                      "date": int(time.time()), "chat": chat}})
        raise web.HTTPNotFound()

    app = web.Application(client_max_size=3 * 1024 ** 2)
    app.router.add_post("/bot{token}/{method}", telegram)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8081)
    await site.start()
    try:
        migrate = await asyncio.create_subprocess_exec(sys.executable, "-m", "elevenbot", "migrate", env=env)
        if await migrate.wait():
            raise SystemExit("Dev migration failed")
        bot = await asyncio.create_subprocess_exec(sys.executable, "-m", "elevenbot", "bot", env=env)
        try:
            raise SystemExit(await bot.wait())
        finally:
            if bot.returncode is None:
                bot.send_signal(signal.SIGINT)
                await bot.wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
