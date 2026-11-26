"""FT-020: session-scoped HTTP image commands using disposable PostgreSQL."""
import asyncio
import base64
import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from elevenbot.aggregate import make_snapshot
from elevenbot.core import Rejected, Service
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import account_db, signed
from test_admin_access import event
from test_ui import Bot


TEST_VIEW = web.AppKey('studio_test_view', TelegramApp)


@pytest.fixture
async def image_api(account_db, monkeypatch, request):
    pool, original = account_db
    cfg = replace(original, mode='clodex', generation_enabled=True, economy_verified=True,
                  clodex_key='fixture-only', interaction_mode='off', interaction_limit=100,
                  public_image_models=('clodex:flux-schnell',), payments_enabled=False)
    offline = getattr(request, 'param', None) == 'mock'
    if offline:
        cfg = replace(cfg, mode='mock', interaction_mode='mock', economy_verified=False, clodex_key='')
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
    app = create_app(pool, cfg, view=view, job_scheduler=None if offline else deferred.append)
    app[TEST_VIEW] = view
    async with TestClient(TestServer(app)) as client:
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


async def test_http_price_fields_are_rejected_without_financial_side_effects(image_api):
    pool, users, client, headers, posts, deferred, _, _ = image_api
    owner, foreign = headers
    quote_request = {'model': 'flux-schnell', 'prompt': 'fixture contract check'}
    job_headers = owner | {'Idempotency-Key': 'fixture_price_contract'}
    extra_fields = ({'price': {'total': '1'}}, {'total': '1'})

    async def wallet_balances():
        return await pool.fetch(
            "SELECT user_id,available,reserved FROM wallets WHERE mode='live' ORDER BY user_id"
        )

    opening_wallets = await wallet_balances()
    assert [(r['available'], r['reserved']) for r in opening_wallets] == [(100, 0), (100, 0)]
    opening_ledger = await pool.fetch('SELECT * FROM ledger ORDER BY id')
    for extra in extra_fields:
        response = await client.post('/api/v1/quotes', headers=owner, json={**quote_request, **extra})
        assert response.status == 400
    assert not await pool.fetchval('SELECT count(*) FROM task_price_quotes')

    response = await client.post('/api/v1/quotes', headers=owner, json=quote_request)
    assert response.status == 201
    quote_data = await response.json()
    quote_id = quote_data['quote_id']
    assert quote_data['price']['total'] == '10'
    for extra in extra_fields:
        response = await client.post('/api/v1/jobs', headers=job_headers, json={'quote_id': quote_id, **extra})
        assert response.status == 400
    assert (await create(client, foreign, quote_id, 'fixture_price_contract')).status == 404
    assert await wallet_balances() == opening_wallets
    assert await pool.fetch('SELECT * FROM ledger ORDER BY id') == opening_ledger
    assert not await pool.fetchval('SELECT count(*) FROM task_dispatch')
    assert not await pool.fetchval('SELECT count(*) FROM http_image_commands')
    assert not posts and not deferred

    response = await client.post('/api/v1/jobs', headers=job_headers, json={'quote_id': quote_id})
    assert response.status == 201
    await deferred.pop()()
    assert posts == ['/v1/images/generations']
    balances = {r['user_id']: (r['available'], r['reserved']) for r in await wallet_balances()}
    assert balances == {users[0]: (90, 0), users[1]: (100, 0)}
    movements = await pool.fetch("""
        SELECT user_id,kind,da,dr FROM ledger WHERE task_quote_id=$1::uuid ORDER BY kind
    """, quote_id)
    assert [tuple(row) for row in movements] == [
        (users[0], 'task_capture', 0, -10),
        (users[0], 'task_reserve', -10, 10),
    ]


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
    foreign_wallet = await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'", users[1])
    assert tuple(foreign_wallet) == (100, 0)
    assert not await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1 AND task_quote_id IS NOT NULL", users[1])
    assert await (await client.get(data['result_url'], headers=headers[0])).read() == MOCK_IMAGE
    works = await (await client.get('/api/v1/works', headers=headers[0])).json()
    work = next(w for w in works['works'] if w['result_url'] == data['result_url'])
    assert work['prompt'] == 'fixture prompt' and work['price'] == '10'
    assert not (await (await client.get('/api/v1/works', headers=headers[1])).json())['works']
    assert await (await client.get(data['result_url'], headers=headers[0])).read() == MOCK_IMAGE
    next_quote = await quote(client, headers[0], work['prompt'])
    assert next_quote != q
    assert posts == ['/v1/images/generations']
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1 AND kind='task_capture'", users[0]) == 1
    rows = await pool.fetch('SELECT kind FROM ledger WHERE task_quote_id=$1::uuid ORDER BY kind', job)
    assert [r['kind'] for r in rows] == ['task_capture','task_reserve']
    assert await pool.fetchval('SELECT correlation_id < 0 FROM http_image_commands WHERE quote_id=$1::uuid', job)


@pytest.mark.parametrize('image_api', ['mock'], indirect=True)
async def test_priced_mock_image_cross_client_delivery(image_api):
    pool, users, client, headers, posts, _, _, _ = image_api
    view = client.app[TEST_VIEW]
    snapshot = view.catalogue_snapshot()

    async def press(update_id, *, text=None, callback=None):
        await view.handle(event(update_id, text, chat=101, callback=callback))

    def button(prefix):
        return next(item.callback_data for _, keyboard in reversed(view.bot.sent)
                    if hasattr(keyboard, 'inline_keyboard')
                    for row in keyboard.inline_keyboard for item in row
                    if (item.callback_data or '').startswith(prefix))

    catalogue = await client.get('/api/v1/catalogue', headers=headers[1])
    assert any(model.get('image_card') for model in (await catalogue.json())['models'])
    await press(1001, callback=f'smodel:{snapshot["version"]}:image:0:0')
    await press(1002, callback=button('srun:'))
    await press(1003, text='Маяк в тумане')
    await press(1004, callback=button('amconfirm:'))
    assert len(view.bot.photos) == 1
    jobs = await (await client.get('/api/v1/jobs', headers=headers[1])).json()
    telegram_job, = jobs['jobs']
    assert telegram_job['origin'] == 'telegram'
    assert telegram_job['state'] == 'completed'
    work_url = telegram_job['result_url']
    assert await (await client.get(work_url, headers=headers[1])).read() == MOCK_IMAGE
    assert (await client.get(work_url, headers=headers[0])).status == 404

    http_quote = await quote(client, headers[1], 'Маяк под снегом')
    assert (await create(client, headers[1], http_quote)).status == 201
    async with asyncio.timeout(5):
        while True:
            result = await (await client.get(f'/api/v1/jobs/{http_quote}', headers=headers[1])).json()
            if result['state'] == 'completed':
                break
            assert result['state'] in ('pending', 'dispatching')
            await asyncio.sleep(.05)
    await press(1005, callback='history:0')
    assert result['origin'] == 'http'
    work_id = result['result_url'].rsplit('/', 1)[-1]
    await press(1006, callback=f'image:{work_id}')
    assert len(view.bot.photos) == 2
    assert all(photo.data == MOCK_IMAGE for photo, _, _ in view.bot.photos)
    assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",
                                     users[1])) == (80, 0)
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1 AND kind='task_capture'", users[1]) == 2
    assert not posts


@pytest.mark.parametrize(('operation', 'kind'), [('video', 'video'), ('audio.speech', 'audio')])
async def test_miniapp_projects_owned_telegram_studio_jobs(image_api, operation, kind):
    pool, users, client, headers, _, _, _, _ = image_api
    job = uuid4()
    await pool.execute("""INSERT INTO task_price_quotes(id,user_id,provider,model_id,operation,request,price,state,
                                                       accepted_at,update_id)
                       VALUES($1,$2,'clodex','fixture',$3,'{}','{}','accepted',now(),701)""",
                       job, users[0], operation)
    await pool.execute("INSERT INTO task_dispatch(quote_id,state) VALUES($1,'completed')", job)
    if kind == 'video':
        await pool.execute("""INSERT INTO video_jobs(id,user_id,model_id,prompt,status,video,expires_at)
                           VALUES($1,$2,'fixture','fixture','succeeded',$3,now()+interval '1 day')""",
                           job, users[0], b'stored video fixture')
    else:
        await pool.execute("""INSERT INTO task_speech_works(id,user_id,model_id,title,input,cost_tokens,claimed,audio)
                           VALUES($1,$2,'fixture','fixture','fixture',0,true,$3)""",
                           job, users[0], b'stored speech fixture')
    response = await client.get(f'/api/v1/jobs/{job}', headers=headers[0])
    assert response.status == 200
    assert await response.json() == {'id': str(job), 'model': 'fixture', 'operation': operation,
                                     'state': 'completed', 'origin': 'telegram',
                                     'result_url': f'/api/v1/works/{kind}/{job}'}
    assert (await client.get(f'/api/v1/jobs/{job}', headers=headers[1])).status == 404


async def test_cancel_pending_is_idempotent_without_provider_post(image_api):
    pool, _, client, headers, posts, deferred, _, _ = image_api
    q = await quote(client, headers[0])
    assert (await create(client, headers[0], q)).status == 201
    for _ in range(2):
        result = await (await client.post('/api/v1/jobs/'+q+'/cancel', headers=headers[0])).json()
        assert result == {'cancelled':True,'state':'cancelled'}
    assert (await (await client.get('/api/v1/jobs/'+q, headers=headers[0])).json())['state'] == 'cancelled'
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
