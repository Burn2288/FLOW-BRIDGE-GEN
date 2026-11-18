"""Transport authorisation boundaries on disposable PostgreSQL, no paid calls."""
from dataclasses import replace

from aiohttp.test_utils import TestClient, TestServer
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed
from test_admin_access import event
from test_ui import Bot


async def test_transports_cannot_bypass_consent_or_use_foreign_quote(env):
    pool, cfg, service, owner = env
    cfg = replace(cfg, token='fixture', payments_enabled=False, platega_enabled=False)
    quote, _ = await service.quote(owner, 'fixture', 'demo')
    guest = await service.identity(101)
    bot = Bot()
    app = TelegramApp(pool, cfg, bot)

    # A callback cannot bypass the common service's consent check.
    await app.handle(event(1, chat=101, callback=f'confirm:{quote}'))
    assert await pool.fetchval('SELECT count(*) FROM jobs') == 0
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='reserve'") == 0
    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        response = await client.post('/api/v1/session', json={'initData': signed('fixture', 101)})
        assert response.status == 403
        assert (await client.get('/api/v1/wallet')).status == 401

    # Consent alone does not confer ownership of another user's quote.
    await service.accept(guest)
    await app.handle(event(2, chat=101, callback=f'confirm:{quote}'))
    assert await pool.fetchval('SELECT count(*) FROM jobs') == 0
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='reserve'") == 0

    # Repeating the legitimate callback goes through the same idempotent service.
    await app.handle(event(3, chat=100, callback=f'confirm:{quote}'))
    await app.handle(event(4, chat=100, callback=f'confirm:{quote}'))
    assert await pool.fetchval('SELECT count(*) FROM jobs WHERE quote_id=$1 AND user_id=$2', quote, owner) == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1 AND kind='reserve'", owner) == 1
    assert await pool.fetchval('SELECT count(*) FROM payments') == 0
