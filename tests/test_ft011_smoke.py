"""Prepared combined smoke: fixture-only PostgreSQL, Telegram transport and image provider."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer
from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed
from test_admin_access import event
from test_telegram_consent import DocumentTransport


async def test_ft010_telegram_consent_mock_library_and_owner(env):
    pool, cfg, service, _ = env
    cfg = replace(cfg, token='fixture', interaction_limit=10, payments_enabled=False,
                  platega_enabled=False, generation_enabled=True)
    bot = DocumentTransport()
    app = TelegramApp(pool, cfg, bot)
    await app.handle(event(1, '/start', chat=101))
    assert bot.trace[:2] == ['terms.md', 'privacy.md']
    offer = bot.trace[2]
    assert offer.startswith('accept:')
    owner = await service.identity(101)
    assert await pool.fetchval('SELECT accepted_at FROM identities WHERE user_id=$1', owner) is None
    await app.handle(event(2, callback=offer, chat=101))
    docs = service.get_consent_documents()
    assert await pool.fetchval('SELECT terms_version FROM identities WHERE user_id=$1', owner) == docs['version']
    async with pool.acquire() as conn:
        await service.authorize(conn, owner)
    adapter = SimpleNamespace(submit_image=AsyncMock(return_value=SimpleNamespace(status=200)),
                              image_result=AsyncMock(return_value=SimpleNamespace(image=MOCK_IMAGE, filename='test.png')),
                              poll_image=AsyncMock())
    jobs = AnyModelImageJobs(pool, cfg, adapter=adapter)
    await jobs.submit(owner, 94401, 'fixture')
    saved = await pool.fetchrow('SELECT id,image FROM image_works WHERE update_id=$1 AND user_id=$2', 94401, owner)
    assert saved and saved['image'] == MOCK_IMAGE and adapter.submit_image.await_count == 1
    other = await service.identity(102)
    await service.accept(other, docs['version'])
    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        own_login = await client.post('/api/v1/session', json={'initData': signed('fixture', 101)})
        other_login = await client.post('/api/v1/session', json={'initData': signed('fixture', 102)})
        assert own_login.status == other_login.status == 200
        own = {'Authorization': 'Bearer ' + (await own_login.json())['token']}
        foreign = {'Authorization': 'Bearer ' + (await other_login.json())['token']}
        assert (await client.get('/api/v1/wallet', headers=own)).status == 200
        response = await client.get('/api/v1/works', headers=own)
        assert any(w['id'] == str(saved['id']) and w['kind'] == 'image' for w in (await response.json())['works'])
        path = '/api/v1/works/image/' + str(saved['id'])
        assert (await client.get(path, headers=foreign)).status == 404
        assert (await client.get(path + '/timeline', headers=foreign)).status == 404
        timeline = await client.get(path + '/timeline', headers=own)
        assert timeline.status == 200 and (await timeline.json())['status'] == 'succeeded'
    bot.send_invoice.assert_not_awaited()
    assert not cfg.payments_enabled and not cfg.platega_enabled
    assert await pool.fetchval('SELECT count(*) FROM payments') == 0


async def test_ft011_document_delivery_failure_does_not_grant_consent(env):
    pool, cfg, service, _ = env
    cfg = replace(cfg, token='fixture', payments_enabled=False, platega_enabled=False)
    bot = DocumentTransport()
    bot.fail_privacy = True
    app = TelegramApp(pool, cfg, bot)
    await app.handle(event(1, '/start', chat=103))
    assert bot.trace == ['terms.md']
    user = await service.identity(103)
    assert await pool.fetchval('SELECT accepted_at FROM identities WHERE user_id=$1', user) is None
    bot.send_invoice.assert_not_awaited()
    assert await pool.fetchval('SELECT count(*) FROM payments') == 0
