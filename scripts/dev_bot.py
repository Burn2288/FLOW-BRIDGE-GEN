"""Start the dev gateway against a loopback Telegram smoke fixture."""

import asyncio
import os
import sys
import time

from aiohttp import web


async def main():
    async def telegram(request):
        method = request.match_info["method"].lower()
        if method == "getupdates":
            form = await request.post()
            if int(form.get("offset", "0")) <= 1:
                message = {
                    "message_id": 1,
                    "date": int(time.time()),
                    "chat": {"id": 100, "type": "private"},
                    "from": {"id": 100, "is_bot": False, "first_name": "Fixture"},
                    "text": "/start",
                }
                return web.json_response({"ok": True, "result": [{"update_id": 1, "message": message}]})
            await asyncio.sleep(0.2)
            return web.json_response({"ok": True, "result": []})
        if method == "sendmessage":
            print("telegram_stub_smoke=ok", flush=True)
            return web.json_response({
                "ok": True,
                "result": {"message_id": 2, "date": int(time.time()), "chat": {"id": 100, "type": "private"}},
            })
        if method == "deletemessage":
            return web.json_response({"ok": True, "result": True})
        raise web.HTTPNotFound()

    app = web.Application()
    app.router.add_post("/bot{token}/{method}", telegram)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8081)
    await site.start()
    env = os.environ | {
        "PROVIDER_MODE": "mock",
        "PAYMENTS_ENABLED": "false",
        "TELEGRAM_BOT_TOKEN": "123456:" + "fixture_" * 5,
        "TELEGRAM_API_BASE": "http://127.0.0.1:8081",
        "ALLOW_LOCAL_TELEGRAM_STUB": "true",
    }
    try:
        migrate = await asyncio.create_subprocess_exec(sys.executable, "-m", "elevenbot", "migrate", env=env)
        if await migrate.wait():
            raise SystemExit("Dev migration failed")
        bot = await asyncio.create_subprocess_exec(sys.executable, "-m", "elevenbot", "bot", env=env)
        try:
            raise SystemExit(await bot.wait())
        finally:
            if bot.returncode is None:
                bot.terminate()
                await bot.wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
