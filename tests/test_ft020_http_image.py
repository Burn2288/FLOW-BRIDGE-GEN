"""FT-020: session-scoped HTTP image commands using disposable PostgreSQL."""
import asyncio
import base64
import json
from dataclasses import replace

import httpx
import pytest
from aiohttp.test_utils import TestClient, TestServer
from elevenbot.aggregate import make_snapshot
from elevenbot.core import Rejected, Service
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import account_db, signed
from test_ui import Bot


@pytest.fixture
async def image_api(account_db, monkeypatch):
    pool, original = account_db
    cfg = replace(original, mode='clodex', generation_enabled=True, economy_verified=True,
                  clodex_key='fixture-only', interaction_mode='off', interaction_limit=100,
                  public_image_models=('clodex:flux-schnell',), payments_enabled=False)
    service = Service(pool, cfg)
    users = []
    for ext in (100, 101):
        user = await service.identity(ext)
        await service.accept(user)
        async with pool.acquire() as conn, conn.transaction():
            await service.movement(conn, user, 'live', f'fixture-credit-{ext}', 'pilot_grant', 100, 0)
        users.append(user)
    snapshot = make_snapshot([{'provider':'clodex', 'id':'flux-schnell', 'title':'FLUX Schnell',
        'operations':['images.generate'], 'protocols':['image-generation'], 'availability':'key_available'}],
        [], [{'provider':'clodex', 'scope':'key_available'}])
    SnapshotStore(cfg.catalogue_path).write(snapshot)
    view = TelegramApp(pool, cfg, Bot())
    await view.pricing.set_tariff(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', {'n':1},
        basis='request', unit='darkflow_token', amount='10', expires=None, evidence='fixture')
    posts, deferred = [], []
    started, release = asyncio.Event(), asyncio.Event()
    async def transport(request):
        assert request.method == 'POST' and request.url.host == 'clodex.xyz'
        posts.append(request.url.path)
        prompt = json.loads(request.content)['prompt']
        if prompt == 'timeout':
            raise httpx.ReadTimeout('fixture timeout', request=request)
        if prompt == 'running':
            started.set()
            await asyncio.wait_for(release.wait(), 10)
        return httpx.Response(200, json={'data':[{'b64_json':base64.b64encode(MOCK_IMAGE).decode()}]})
    original_client = httpx.AsyncClient
    def fixture_client(*args, **kwargs):
        return original_client(*args, **(kwargs | {'transport':httpx.MockTransport(transport)}))
    monkeypatch.setattr(httpx, 'AsyncClient', fixture_client)
    async with TestClient(TestServer(create_app(pool, cfg, view=view, job_scheduler=deferred.append))) as client:
        headers = []
        for ext in (100,101):
            response = await client.post('/api/v1/session', json={'initData':signed(cfg.token, ext)})
            assert response.status == 200
            headers.append({'Authorization':'Bearer '+(await response.json())['token']})
        yield pool, users, client, headers, posts, deferred, started, release


async def quote(client, headers, prompt='fixture prompt'):
    response = await client.post('/api/v1/quotes', headers=headers, json={'model':'flux-schnell','prompt':prompt})
    assert response.status == 201, await response.text()
    return (await response.json())['quote_id']


async def create(client, headers, quote_id, key='fixture_key_01'):
    return await client.post('/api/v1/jobs', headers=headers | {'Idempotency-Key':key}, json={'quote_id':quote_id})


async def test_http_image_end_to_end_idempotency_and_isolation(image_api):
    pool, users, client, headers, posts, deferred, _, _ = image_api
    q = await quote(client, headers[0])
    assert (await create(client, headers[1], q)).status == 404
    response = await create(client, headers[0], q)
    assert response.status == 201, await response.text()
    job = (await response.json())['id']
    assert job == q and len(deferred) == 1
    assert (await create(client, headers[0], q)).status == 200
    other_q = await quote(client, headers[0], 'other')
    assert (await create(client, headers[0], other_q)).status == 409
    assert (await client.get('/api/v1/jobs/'+job, headers=headers[1])).status == 404
    assert not (await (await client.get('/api/v1/jobs', headers=headers[1])).json())['jobs']
    assert len((await (await client.get('/api/v1/jobs', headers=headers[0])).json())['jobs']) == 1
    assert (await client.post('/api/v1/jobs/'+job+'/cancel', headers=headers[1])).status == 404
    await deferred.pop()()
    response = await client.get('/api/v1/jobs/'+job, headers=headers[0])
    data = await response.json()
    assert data['state'] == 'completed' and data['origin'] == 'http' and data['result_url']
    assert posts == ['/v1/images/generations']
    assert (await client.get(data['result_url'], headers=headers[1])).status == 404
    assert await (await client.get(data['result_url'], headers=headers[0])).read() == MOCK_IMAGE
    works = await (await client.get('/api/v1/works', headers=headers[0])).json()
    assert any(w['result_url'] == data['result_url'] for w in works['works'])
    rows = await pool.fetch('SELECT kind FROM ledger WHERE task_quote_id=$1::uuid ORDER BY kind', job)
    assert [r['kind'] for r in rows] == ['task_capture','task_reserve']
    assert await pool.fetchval('SELECT correlation_id < 0 FROM http_image_commands WHERE quote_id=$1::uuid', job)


async def test_cancel_pending_is_idempotent_without_provider_post(image_api):
    pool, _, client, headers, posts, deferred, _, _ = image_api
    q = await quote(client, headers[0])
    assert (await create(client, headers[0], q)).status == 201
    for _ in range(2):
        result = await (await client.post('/api/v1/jobs/'+q+'/cancel', headers=headers[0])).json()
        assert result == {'cancelled':True,'state':'interrupted'}
    with pytest.raises(Rejected):
        await deferred.pop()()
    assert not posts
    rows = await pool.fetch('SELECT kind FROM ledger WHERE task_quote_id=$1::uuid ORDER BY kind', q)
    assert [r['kind'] for r in rows] == ['task_release','task_reserve']


async def test_no_cancel_after_submission_or_unknown(image_api):
    pool, _, client, headers, posts, deferred, _, _ = image_api
    q = await quote(client, headers[0])
    assert (await create(client, headers[0], q)).status == 201
    await pool.execute("UPDATE task_dispatch SET state='uncertain' WHERE quote_id=$1::uuid", q)
    result = await (await client.post('/api/v1/jobs/'+q+'/cancel', headers=headers[0])).json()
    assert result == {'cancelled':False,'state':'uncertain'}
    with pytest.raises(Rejected):
        await deferred.pop()()
    assert not posts
    assert not await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1::uuid AND kind='task_release'",q)


async def test_mock_timeout_never_reposts_or_releases_unknown(image_api):
    pool, _, client, headers, posts, deferred, _, _ = image_api
    q = await quote(client, headers[0], 'timeout')
    assert (await create(client, headers[0], q)).status == 201
    with pytest.raises(Rejected):
        await deferred.pop()()
    result = await (await client.post('/api/v1/jobs/'+q+'/cancel', headers=headers[0])).json()
    assert result == {'cancelled':False, 'state':'uncertain'}
    assert (await create(client, headers[0], q)).status == 200
    assert posts == ['/v1/images/generations'] and not deferred
    assert not await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1::uuid AND kind='task_release'",q)


async def test_cancel_while_provider_post_inflight_does_not_release(image_api):
    pool, _, client, headers, posts, deferred, started, release = image_api
    q = await quote(client, headers[0], 'running')
    assert (await create(client, headers[0], q)).status == 201
    running = asyncio.create_task(deferred.pop()())
    try:
        await asyncio.wait_for(started.wait(), 5)
        result = await (await client.post('/api/v1/jobs/'+q+'/cancel', headers=headers[0])).json()
        assert result == {'cancelled':False, 'state':'dispatching'}
        assert not await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1::uuid AND kind='task_release'",q)
    finally:
        release.set()
        await running
    assert posts == ['/v1/images/generations']
    assert await pool.fetchval("SELECT state FROM task_dispatch WHERE quote_id=$1::uuid",q) == 'completed'
