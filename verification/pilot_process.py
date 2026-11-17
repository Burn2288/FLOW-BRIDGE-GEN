"""Test-only subprocess: real TelegramApp or Mini App, fake bot, loopback control."""
import asyncio
import json
import os
import sys
from pathlib import Path
import asyncpg
from aiohttp import web

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from scripts.disposable_test_db import require_disposable_dsn
from elevenbot.config import Config
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from test_private_pilot import telegram_event
from test_ui import Bot


class RecordingBot(Bot):
    async def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))


async def main():
    dsn = require_disposable_dsn(os.environ)
    schema = os.environ['PILOT_FIXTURE_SCHEMA']
    if not schema.startswith('test_') or not schema[5:].isalnum():
        raise ValueError('fixture schema invalid')
    cfg = Config.env()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3,
                                     server_settings={'search_path': schema})
    if os.environ['PILOT_FIXTURE_KIND'] == 'telegram':
        bot = RecordingBot()
        tg = TelegramApp(pool, cfg, bot)
        app = web.Application()

        async def dispatch(request):
            data = await request.json()
            bot.sent.clear()
            bot.answers.clear()
            event = telegram_event(data['user'], text=data.get('text', '/start'),
                                   callback=data.get('callback'))
            await tg.handle(event)
            text = ' '.join(str(x[0]) for x in bot.sent)
            text += ' '.join(str(item[1].get('text', '')) for item in bot.answers)
            return web.json_response({'denied': 'ограничен' in text.lower(),
                                      'admin': tg.has_admin_session(data['user'])})
        app.router.add_post('/fixture/telegram', dispatch)
    else:
        app = create_app(pool, cfg)

    async def metadata(request):
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT current_database() AS db, current_schema() AS schema, pg_backend_pid() AS backend')
        return web.json_response({'pid': os.getpid(), 'db': row['db'], 'schema': row['schema'],
                                  'backend': row['backend'], 'tester_allowed': 101 in cfg.pilot_user_ids})
    app.router.add_get('/fixture/metadata', metadata)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    print(json.dumps({'port': site._server.sockets[0].getsockname()[1]}), flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
