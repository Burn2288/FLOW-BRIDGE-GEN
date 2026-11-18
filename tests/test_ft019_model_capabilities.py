"""MC-01: PostgreSQL model-version and existing quote/dispatch boundaries."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
from unittest.mock import AsyncMock

import httpx
import pytest

from elevenbot.core import Rejected
from elevenbot.pricing import NoProviderPrice, Request
from test_provider_extensibility import app_with_fixture
from test_ui import Bot


async def test_versioned_quotes_and_dispatch_preserve_snapshots(env, confirmed_credit):
    pool, cfg, _, user = env
    posts = []
    def respond(request):
        posts.append(request.url.path)
        return httpx.Response(200, json={'answer': 'mock result'})
    async with httpx.AsyncClient(base_url='https://fixture.invalid', transport=httpx.MockTransport(respond)) as client:
        app = app_with_fixture(pool, cfg, Bot(), client)
        app.pricing.adapters['fixture'].cost = AsyncMock(side_effect=NoProviderPrice)
        await pool.execute("INSERT INTO approved_models VALUES('fixture','fixture/chat','chat','Fixture')")
        await confirmed_credit(pool, cfg, user, 1000)
        params = {'max_tokens': 100}
        await app.pricing.set_tariff(user, 100, 'fixture', 'fixture/chat', 'chat', params,
            basis='request', unit='darkflow_token', amount='10', evidence='fixture')
        policy = app.models
        schema_a = {'properties': {'max_tokens': {'type': 'integer', 'minimum': 1, 'maximum': 200}}, 'required': ['max_tokens']}
        a = await policy.stage_capabilities(user, 100, 'fixture', 'fixture/chat', 'chat', schema_a)
        await policy.publish_capabilities(user, 100, 'fixture', 'fixture/chat', 'chat', a)
        bad_schema = deepcopy(schema_a)
        bad_schema['properties']['max_tokens']['maximum'] = 'secret-value'
        with pytest.raises(Rejected):
            await policy.stage_capabilities(user, 100, 'fixture', 'fixture/chat', 'chat', bad_schema)
        assert await pool.fetchval('SELECT version FROM model_capability_versions WHERE published') == a
        req = Request('fixture', 'fixture/chat', 'chat', 'Fixture', 'prompt', params)
        for bad in ({'max_tokens': 201}, {'max_tokens': 100, 'extra': 1}):
            with pytest.raises(Rejected):
                await app.pricing.quote(user, replace(req, params=bad))
        assert not posts and not await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='task_reserve'")
        quote_a = await app.pricing.quote(user, req)
        assert quote_a.request.model_version == {'version': str(a), 'schema': schema_a}
        schema_b = deepcopy(schema_a)
        schema_b['properties']['max_tokens']['maximum'] = 120
        b = await policy.stage_capabilities(user, 100, 'fixture', 'fixture/chat', 'chat', schema_b)
        await policy.publish_capabilities(user, 100, 'fixture', 'fixture/chat', 'chat', b)
        accepted, ok, _ = await app.launch.confirm(user, 100, quote_a.id, 9191,
            progress=lambda _: nullcontext(), background=None)
        assert ok and accepted.request.model_version == quote_a.request.model_version
        assert posts == ['/generate']
        stored = await pool.fetchval('SELECT request::text FROM task_price_quotes WHERE id=$1', quote_a.id)
        import json
        assert json.loads(stored)['model_version']['version'] == str(a)
        with pytest.raises(Rejected):
            await app.launch.confirm(user, 100, quote_a.id, 9192, progress=lambda _: nullcontext(), background=None)
        assert posts == ['/generate']
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_reserve'", quote_a.id) == 1
        from elevenbot.pricing import Pricing
        restarted = Pricing(pool, app.cfg, app.pricing.adapters)
        quote_b = await restarted.quote(user, req)
        assert quote_b.request.model_version['version'] == str(b)
        await pool.execute("DELETE FROM approved_models WHERE provider='fixture' AND model_id='fixture/chat' AND operation='chat'")
        with pytest.raises(Rejected):
            await app.launch.confirm(user, 100, quote_b.id, 9193, progress=lambda _: nullcontext(), background=None)
        assert await pool.fetchval('SELECT state FROM task_dispatch WHERE quote_id=$1', quote_a.id) == 'completed'
        assert posts == ['/generate']
        assert (await pool.fetchval('SELECT count(*) FROM model_capability_versions')) == 2


def test_schema_rejects_unsupported_or_duplicate_rules():
    from elevenbot.model_capabilities import validate_schema
    for schema in ({'properties': {'n': {'type': 'string'}}, 'required': []},
                   {'properties': {'n': {'type': 'integer'}}, 'required': ['n', 'n']},
                   {'properties': {'n': {'type': 'integer', 'minimum': 4, 'maximum': 1}}, 'required': []}):
        with pytest.raises(Rejected):
            validate_schema(schema)


async def test_telegram_and_miniapp_catalogues_share_revoke(account_db):
    from aiohttp.test_utils import TestClient, TestServer
    from elevenbot.aggregate import make_snapshot
    from elevenbot.core import Service
    from elevenbot.discovery import SnapshotStore
    from elevenbot.telegram import TelegramApp
    from miniapp.backend.web import create_app
    from miniapp.tests.test_miniapp import signed

    pool, cfg = account_db
    service = Service(pool, cfg)
    user = await service.identity(100)
    await service.accept(user)
    models = [{'provider': 'clodex', 'id': 'fixture/image', 'title': 'Fixture',
               'availability': 'key_available', 'operations': ['images.generate']}]
    snap = make_snapshot(models, [], [{'provider': 'clodex', 'scope': 'key_available'}])
    SnapshotStore(cfg.catalogue_path).write(snap)
    await pool.execute("INSERT INTO approved_models VALUES('clodex','fixture/image','images.generate','Fixture')")
    bot = TelegramApp(pool, cfg, Bot())
    policy = bot.models
    schema = {'properties': {'n': {'type': 'integer', 'minimum': 1, 'maximum': 1}}, 'required': []}
    version = await policy.stage_capabilities(user, 100, 'clodex', 'fixture/image', 'images.generate', schema)
    await policy.publish_capabilities(user, 100, 'clodex', 'fixture/image', 'images.generate', version)
    assert await bot.store_models(snap, 'image', None) == [0]
    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        response = await client.post('/api/v1/session', json={'initData': signed(cfg.token, 100)})
        assert response.status == 200
        headers = {'Authorization': 'Bearer ' + (await response.json())['token']}
        result = await (await client.get('/api/v1/catalogue', headers=headers)).json()
        assert 'fixture/image' in [model['id'] for model in result['models']]
        policy.show = AsyncMock()
        await policy.command(user, 100, '/revoke', ['clodex', 'fixture/image', 'images.generate'])
        assert await bot.store_models(snap, 'image', None) == []
        result = await (await client.get('/api/v1/catalogue', headers=headers)).json()
        assert 'fixture/image' not in [model['id'] for model in result['models']]
        assert await pool.fetchval('SELECT count(*) FROM model_capability_versions WHERE version=$1', version) == 1


from miniapp.tests.test_miniapp import account_db
