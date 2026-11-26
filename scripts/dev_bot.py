"""Run the local, unpaid studio fixture and expose its Telegram transport."""

import asyncio
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

from aiohttp import web

TOKEN = "123456:" + "fixture_" * 5


def fixture_environment():
    from urllib.parse import urlsplit

    dsn = os.environ.get("DATABASE_URL", "")
    db = urlsplit(dsn)
    if (db.scheme != "postgresql" or db.netloc != "postgres:isolated-test-only@127.0.0.1:5432"
            or db.path != "/flowbridge_dev" or db.query or db.fragment):
        raise SystemExit("DEV requires its dedicated loopback flowbridge_dev database")
    root = Path(__file__).resolve().parents[1]
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "AUDIO_STORAGE_DIR")
           if key in os.environ}
    return env | {
        "DATABASE_URL": dsn,
        "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root))),
        "PYTHONUNBUFFERED": "1",
        "PROVIDER_MODE": "mock",
        "GENERATION_ENABLED": "true",
        "PAYMENTS_ENABLED": "false",
        "TELEGRAM_BOT_TOKEN": TOKEN,
        "TELEGRAM_API_BASE": "http://127.0.0.1:8081",
        "ALLOW_LOCAL_TELEGRAM_STUB": "true",
        "RF02_FUNCTIONAL_TEST": "YES",
        "FLOWBRIDGE_DEV_FIXTURE": "YES",
    }


class TelegramFixture:
    def __init__(self, pool, cfg, update_id):
        self.pool = pool
        self.cfg = cfg
        self.next_update = update_id
        self.updates = deque()
        self.replies = deque(maxlen=1000)
        self.sequence = 0
        self.next_message = int(time.time())
        self.stars_events = {}
        self.stars_lock = asyncio.Lock()

    @staticmethod
    def chat(external):
        return {"id": external, "type": "private"}

    async def submit(self, request):
        value = await request.json()
        if not isinstance(value, dict) or set(value) - {"chat", "text", "callback", "message_id"}:
            raise web.HTTPBadRequest()
        chat, text, callback = value.get("chat"), value.get("text"), value.get("callback")
        if chat not in (100, 101, 102, 103, 104) or type(chat) is not int:
            raise web.HTTPBadRequest()
        data = callback if callback is not None else text
        if ((callback is None) == (text is None) or not isinstance(data, str) or not data
                or len(data.encode()) > (64 if callback is not None else 16000)):
            raise web.HTTPBadRequest()
        if len(self.updates) >= 256:
            raise web.HTTPTooManyRequests()
        message_id = value.get("message_id", self.next_message + 1)
        if type(message_id) is not int or not 0 < message_id <= 2**31 - 1:
            raise web.HTTPBadRequest()
        payload = {"text": text} if callback is None else {}
        number = self.enqueue(chat, payload, message_id, callback)
        return web.json_response({"update_id": number}, status=201)

    def enqueue(self, chat, payload, message_id, callback=None):
        self.next_message = max(message_id, self.next_message)
        number = self.next_update
        self.next_update += 1
        actor = {"id": chat, "is_bot": False, "first_name": "Fixture"}
        message = {"message_id": message_id, "date": int(time.time()), "chat": self.chat(chat), "from": actor}
        if callback is None:
            update = {"message": message | payload}
        else:
            message["from"] = {"id": 123456, "is_bot": True, "first_name": "Fixture bot"}
            update = {"callback_query": {"id": str(number), "from": actor, "chat_instance": str(chat),
                                         "message": message, "data": callback}}
        self.updates.append(update | {"update_id": number})
        return number

    async def stars_payment(self, request):
        from dev_finance import successful_payment
        from elevenbot.core import Rejected

        payload = await request.json()
        if not isinstance(payload, dict) or set(payload) - {"chat", "replay"}:
            raise web.HTTPBadRequest()
        chat, replay = payload.get("chat"), payload.get("replay", False)
        if type(chat) is not int or chat not in (103, 104) or type(replay) is not bool:
            raise web.HTTPBadRequest()
        async with self.stars_lock:
            if len(self.updates) >= 256:
                raise web.HTTPTooManyRequests()
            if replay:
                fields = self.stars_events.get(chat)
                if fields is None:
                    raise web.HTTPConflict(text="No fixture payment has been submitted for this actor.")
            else:
                try:
                    fields = await successful_payment(self.pool, self.cfg, chat)
                except Rejected:
                    raise web.HTTPConflict(text="Fixture payment is unavailable for this actor.") from None
                self.stars_events[chat] = fields
            number = self.enqueue(chat, {"successful_payment": fields}, self.next_message + 1)
        return web.json_response({"update_id": number}, status=201)

    async def list_replies(self, request):
        try:
            after = int(request.query.get("after", 0))
        except ValueError:
            raise web.HTTPBadRequest() from None
        return web.json_response({"replies": [item for item in self.replies if item["sequence"] > after]})

    async def music_grant(self, request):
        from elevenbot.clodex_music import request as music_request
        from elevenbot.core import Rejected
        from elevenbot.telegram import TelegramApp

        payload = await request.json()
        chat = payload.get("chat") if isinstance(payload, dict) else None
        if type(chat) is not int or chat not in (100, 102):
            raise web.HTTPBadRequest()
        app = TelegramApp(self.pool, self.cfg, None)
        try:
            user = await app.svc.identity(chat)
            async with self.pool.acquire() as conn, conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(921195,$1)", chat)
                if await conn.fetchval("""
                    SELECT EXISTS(SELECT 1 FROM clodex_music_ledger
                                  WHERE user_id=$1 AND provider='clodex' AND kind='credit')
                """, user):
                    return web.json_response({"granted": 0})
                quote = await app.pricing.quote(user, music_request("Synthetic pilot grant"))
                credit = await app.music.grant(user, chat, quote.id)
        except Rejected:
            raise web.HTTPConflict(text="Accept the current terms first.") from None
        finally:
            await app.topups.client.close()
        return web.json_response({"granted": credit})

    async def api(self, request):
        if request.match_info["token"] != TOKEN:
            raise web.HTTPNotFound()
        method = request.match_info["method"].lower()
        form = await request.post()
        if method == "getupdates":
            offset = int(form.get("offset", "0"))
            while self.updates and self.updates[0]["update_id"] < offset:
                self.updates.popleft()
            if not self.updates:
                await asyncio.sleep(0.15)
            return web.json_response({"ok": True, "result": list(self.updates)})
        if method in ("setmycommands", "setchatmenubutton"):
            return web.json_response({"ok": True, "result": True})
        if method not in ("sendmessage", "sendphoto", "sendaudio", "sendvideo", "sendanimation",
                          "senddocument", "editmessagetext", "editmessagecaption",
                          "deletemessage", "answercallbackquery"):
            raise web.HTTPNotFound()
        self.next_message += 1
        message_id = int(form.get("message_id", self.next_message))
        chat = int(form.get("chat_id", 0))
        media = next((part for part in form.values() if isinstance(part, web.FileField)), None)
        media_sha256 = hashlib.file_digest(media.file, "sha256").hexdigest() if media else None
        self.sequence += 1
        self.replies.append({
            "sequence": self.sequence, "method": method, "chat": chat, "message_id": message_id,
            "text": form.get("text", form.get("caption", "")),
            "reply_markup": json.loads(form.get("reply_markup", "{}")), "media_sha256": media_sha256,
        })
        if method in ("deletemessage", "answercallbackquery"):
            return web.json_response({"ok": True, "result": True})
        return web.json_response({"ok": True, "result": {"message_id": message_id,
                                  "date": int(time.time()), "chat": self.chat(chat)}})

    def app(self):
        app = web.Application(client_max_size=8 * 1024 ** 2)
        app.router.add_post("/bot{token}/{method}", self.api)
        app.router.add_post("/fixture/updates", self.submit)
        app.router.add_get("/fixture/replies", self.list_replies)
        app.router.add_post("/fixture/music-grant", self.music_grant)
        app.router.add_post("/fixture/stars-payment", self.stars_payment)
        return app


async def main():
    env = fixture_environment()
    args = sys.argv[1:]
    if args and args not in (["worker"], ["miniapp"], ["--runtime", "worker"], ["--runtime", "miniapp"],
                              ["--runtime", "bot"]):
        raise SystemExit("usage: dev_bot.py [worker|miniapp]")
    if args in (["worker"], ["miniapp"]):
        os.execve(sys.executable, [sys.executable, __file__, "--runtime", args[0]], env)

    # Revalidate and replace the environment before loading any fixture runtime.
    os.environ.clear()
    os.environ.update(env)
    from dev_runtime import dev_config, offline_clients, seed
    cfg = dev_config()
    if args:
        from elevenbot.__main__ import main as runtime
        sys.argv = [sys.argv[0], args[1]]
        with offline_clients():
            await runtime(config_override=cfg)
        return

    with offline_clients():
        await gateway(cfg, env, seed)


async def gateway(cfg, env, seed):
    from elevenbot.db import connect, migrate
    pool = await connect(cfg.dsn)
    try:
        await migrate(pool)
        await seed(pool, cfg)
        offset = await pool.fetchval("SELECT offset_id FROM poll_state WHERE id=1")
        fixture = TelegramFixture(pool, cfg, max(1, offset))
        runner = web.AppRunner(fixture.app(), access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, "0.0.0.0", 8081).start()
            bot = await asyncio.create_subprocess_exec(sys.executable, __file__, "--runtime", "bot", env=env)
            try:
                raise SystemExit(await bot.wait())
            finally:
                if bot.returncode is None:
                    bot.send_signal(signal.SIGINT)
                    await bot.wait()
        finally:
            await runner.cleanup()
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
