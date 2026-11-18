"""Integrated functional smoke on disposable PostgreSQL and mock transports only."""
from dataclasses import replace
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer
from elevenbot.providers import MockProvider
from elevenbot.telegram import TelegramApp
from elevenbot.worker import Worker
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed
from test_ml01_delivery_recovery import seeded, due, rejected
from test_ui import Bot


async def test_ft006_integrated_smoke(env):
    pool, cfg, service, user = env
    assert cfg.mode == 'mock' and not cfg.payments_enabled
    docs = service.get_consent_documents()
    assert docs['test_only'] and docs['version'] == '1'
    await service.accept(user, docs['version'])
    async with pool.acquire() as conn:
        assert await service.has_current_consent(conn, user)
    quote, _ = await service.quote(user, 'smoke', 'demo')
    job = await service.confirm(user, quote)
    assert (await service.owned(user, job))['status'] == 'queued'
    provider = MockProvider()
    worker = Worker(pool, cfg, provider)
    assert await worker.run_one()
    assert (await service.owned(user, job))['status'] == 'succeeded'
    assert provider.calls == 1

    pool, cfg, service, user, adapter, jobs, image, ledger = await seeded(env)
    cfg = replace(cfg, token='fixture', payments_enabled=False)
    bot = Bot()
    bot.send_photo = AsyncMock(side_effect=rejected('bad request fixture'))
    await due(pool)
    assert await jobs.poll_one(bot)
    bot.send_photo = AsyncMock()
    await TelegramApp(pool, cfg, bot).open_work(user, 100, 'image', str(image['id']))
    assert bot.send_photo.await_args.args[1].data == image['image']
    assert adapter.submit_image.await_count == 1

    other = await service.identity(101)
    await service.accept(other, docs['version'])
    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        response = await client.post('/api/v1/session', json={'initData': signed('fixture', 100)})
        assert response.status == 200
        owner_headers = {'Authorization': 'Bearer ' + (await response.json())['token']}
        wallet = await client.get('/api/v1/wallet', headers=owner_headers)
        assert wallet.status == 200 and set(await wallet.json()) == {'available', 'reserved'}
        works = await client.get('/api/v1/works', headers=owner_headers)
        assert works.status == 200
        image_rows = [row for row in (await works.json())['works'] if row['id'] == str(image['id'])]
        assert len(image_rows) == 1 and image_rows[0]['kind'] == 'image' and image_rows[0]['available']
        response = await client.post('/api/v1/session', json={'initData': signed('fixture', 101)})
        assert response.status == 200
        other_headers = {'Authorization': 'Bearer ' + (await response.json())['token']}
        assert (await client.get('/api/v1/works/image/' + str(image['id']), headers=other_headers)).status == 404
    assert adapter.submit_image.await_count == 1 and provider.calls == 1
    assert not cfg.payments_enabled and await pool.fetchval('SELECT count(*) FROM payments') == 0
    print('CONSENT=PASS QUEUE=PASS IMAGE_RECOVERY=PASS LIBRARY=PASS FOREIGN_IMAGE=404 PAYMENTS=0')
