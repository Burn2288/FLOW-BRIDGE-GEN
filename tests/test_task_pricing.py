import asyncio
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest

from elevenbot.anymodel import AnyModelProvider, model_store
from elevenbot.anymodel_pricing import AnyModelPricing, UNIT, tariff
from elevenbot.core import Rejected
from elevenbot.pricing import PriceUnavailable, Pricing, ProviderCost, Request
from elevenbot.telegram import TelegramApp
from test_anymodel import routes
from test_ui import Bot, event


async def test_new_model_from_catalogue_and_unknown_billing(funded_env, tmp_path, monkeypatch):
    pool, cfg, _, user = funded_env
    cfg = replace(cfg, access_mode='private', admin_ids=(100,), anymodel_test_enabled=True,
                  anymodel_chat_live=True, anymodel_key='fixture', interaction_limit=10,
                  catalogue_path=str(tmp_path/'models.json'))
    known, unknown = 'fixture/new-chat', 'fixture/new-unknown'
    posts = []

    def respond(http_request):
        if http_request.url.path in ('/v1/models/video','/v1/models/tts'):
            return httpx.Response(200,json={'data':[]})
        if http_request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [
                {'id': known, 'name': 'New model', 'kind': 'chat'},
                {'id': unknown, 'name': 'Unknown model', 'kind': 'chat'},
            ]})
        if http_request.url.path == '/v1/models/info':
            model = http_request.url.params['id']
            return httpx.Response(200, json={'id': model, 'endpoint': '/v1/chat/completions',
                'billing': {'unit': 'token' if model == known else 'unsupported',
                            'coefficient': {'input': 0, 'output': 1}}})
        posts.append(http_request)
        return httpx.Response(200, json={'choices':[{'message':{'content':'Fixture reply'}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        api = AnyModelProvider(cfg.anymodel_key, client=http)
        data = await api.refresh(model_store(cfg))
        app = TelegramApp(pool, cfg, Bot())
        monkeypatch.setattr('elevenbot.telegram.AnyModelProvider', lambda key: api)
        app.pricing.adapters['anymodel'] = AnyModelPricing(cfg.anymodel_key, api=api)
        await pool.executemany("INSERT INTO approved_models VALUES('anymodel',$1,'chat',$2)",
                               [(known,'New model'),(unknown,'Unknown model')])
        await app.pricing.set_rule(user,100,'','','percent','25')
        await app.callback(user,100,'amsection:chat')
        await app.callback(user,100,routes(app.bot)['New model'])
        await app.callback(user,100,routes(app.bot)['Рассчитать стоимость'])
        await app.handle(event('hello'))
        assert 'Оценка: 320' in app.bot.sent[-1][0]
        assert set(routes(app.bot)) == {'Генерировать','Отмена'}
        old = routes(app.bot)['Генерировать']
        assert not posts
        await app.pricing.set_rule(user,100,'anymodel',known,'fixed','10')
        await app.callback(user,100,old,request_id=2)
        assert 'Оценка: 266' in app.bot.sent[-1][0]
        assert not posts
        old = routes(app.bot)['Генерировать']
        await app.callback(user,100,'amparams')
        await app.callback(user,100,routes(app.bot)['Лимит ответа · 128'])
        with pytest.raises(Rejected):
            await app.callback(user,100,old,request_id=3)
        await app.handle(event('hello'))
        assert 'Оценка: 138' in app.bot.sent[-1][0]
        assert not posts
        new = routes(app.bot)['Генерировать']
        results = await asyncio.gather(*(app.callback(user,100,new,request_id=i) for i in (3,4)),
                                       return_exceptions=True)
        assert len(posts) == 1 and sum(isinstance(r,Rejected) for r in results) == 1
        assert known.encode() in posts[0].content and b'"max_tokens":128' in posts[0].content
        await app.callback(user,100,'amsection:chat')
        await app.callback(user,100,routes(app.bot)['Unknown model'])
        await app.callback(user,100,routes(app.bot)['Рассчитать стоимость'])
        await app.handle(event('another prompt'))
        assert 'Цена недоступна' in app.bot.sent[-1][0]
        assert 'Генерировать' not in routes(app.bot)
        assert len(posts) == 1


async def test_pricing_policy_refresh_cancel_and_accounting(env):
    pool, cfg, _, user = env
    cfg = replace(cfg, admin_ids=(100,), interaction_limit=10)
    req = Request('anymodel','fixture/new','chat','Fixture','prompt')
    unit = 'fixture_provider_unit'

    class Adapter:
        async def cost(self, request):
            return ProviderCost(Decimal('100'),unit,True,'fixture','answer max 256')

    pricing = Pricing(pool,cfg,{'anymodel':Adapter()})
    with pytest.raises(PriceUnavailable):
        await pricing.quote(user,req)
    with pytest.raises(Rejected):
        await pricing.set_rule(user,101,'','','percent','99')
    await pricing.set_rate(user,100,unit,'1')
    zero = await pricing.quote(user,req)
    assert (zero.price['total'],zero.price['markup']) == ('100','0')
    await pricing.set_rule(user,100,'','','percent','25')
    global_quote = await pricing.quote(user,req)
    assert global_quote.price['total'] == '125'
    await pricing.set_rule(user,100,'anymodel','','fixed','7')
    provider_quote = await pricing.quote(user,req)
    assert provider_quote.price['total'] == '107'
    await pricing.set_rule(user,100,'anymodel',req.model,'percent','25')
    await pricing.set_rate(user,100,unit,'1.01')
    accepted = []

    async def prepare(conn, quote):
        accepted.append(quote.id)

    renewed, ok = await pricing.confirm(user,provider_quote.id,10,prepare)
    assert not ok and renewed.price['total'] == '127' and renewed.price['base'] == '101.00'
    assert not accepted
    await pool.execute("UPDATE task_price_quotes SET expires_at=now()-interval '1 second' WHERE id=$1",renewed.id)
    renewed, ok = await pricing.confirm(user,renewed.id,11,prepare)
    assert not ok and await pricing.cancel(user,renewed.id)
    with pytest.raises(Rejected):
        await pricing.confirm(user,renewed.id,12,prepare)
    quote = await pricing.quote(user,req)
    assert (await pricing.confirm(user,quote.id,13,prepare))[1]
    with pytest.raises(Rejected):
        await pricing.confirm(user,quote.id,14,prepare)
    assert accepted == [quote.id]
    report = await pricing.report(user,100)
    assert report['revenue'] is None and report['actual_margin'] is None
    assert report['estimated_margin'] == Decimal('26')
    await pricing.reconcile(user,100,quote.id,'127','2','100','fixture-evidence')
    report = await pricing.report(user,100)
    assert (report['revenue'],report['actual_cost'],report['actual_margin']) == (125,101,24)
    assert report['estimated_margin'] is None


def test_image_scale_order_and_video_mode():
    req = Request('anymodel','fixture/image','images.generate','Image','draw',{'n':3,'quality':'high','size':'small'})
    metadata = {'id':req.model,'endpoint':'/v1/images/generations','params':['quality','size'],
                'billing':{'unit':'image','base_tokens':101,'coefficient':{'output':0.95},
                           'scales':{'quality':{'high':2},'size':{'small':0.25}}}}
    assert tariff(metadata,req).amount == 146  # ceil(round_half_up(50.5) * 3 * 0.95)
    req = Request('anymodel','fixture/video','video','Video','draw',
                  {'duration':4,'resolution':'480p','aspect_ratio':'16:9','mode':'fast'})
    metadata = {'id':req.model,'endpoint':'/v1/videos/generations','params':list(req.params),
                'billing':{'unit':'second','coefficient':{'output':1.5},'rates':{'fast':{'480p':10}}}}
    assert tariff(metadata,req).amount == 60
    with pytest.raises(PriceUnavailable):
        tariff(metadata,replace(req,params=req.params|{'mode':'unknown'}))

async def test_pc01_confirm_preserves_presented_snapshot_during_rate_change(env):
    pool, cfg, _, owner = env
    checking, resume = asyncio.Event(), asyncio.Event()

    class Adapter:
        wait = False

        async def cost(self, request):
            if self.wait:
                checking.set()
                await asyncio.wait_for(resume.wait(), 5)
            return ProviderCost(Decimal('1'), 'fixture_unit', False, 'fixture', '1 request')

    adapter = Adapter()
    pricing = Pricing(pool, replace(cfg, admin_ids=(100,), interaction_limit=10), {'anymodel':adapter})
    request = Request('anymodel', 'fixture/chat', 'chat', 'Fixture', 'prompt')
    await pricing.set_rate(owner, 100, 'fixture_unit', '1.1')
    shown = await pricing.quote(owner, request)
    query = 'SELECT price::text FROM task_price_quotes WHERE id=$1'
    before = await pool.fetchval(query, shown.id)
    prepared = []

    async def prepare(conn, quote):
        prepared.append(quote.price)

    adapter.wait = True
    confirmation = asyncio.create_task(pricing.confirm(owner, shown.id, 901, prepare))
    try:
        await asyncio.wait_for(checking.wait(), 5)
        await pricing.set_rate(owner, 100, 'fixture_unit', '1.2')
    finally:
        resume.set()
        accepted, ok = await confirmation
    assert ok and accepted.id == shown.id
    assert prepared == [shown.price] and shown.price['total'] == '2'
    assert await pool.fetchval(query, shown.id) == before
    next_quote = await pricing.quote(owner, request)
    assert next_quote.price['total'] == '2'
    assert Decimal(next_quote.price['rate']) == Decimal('1.2')
    assert next_quote.price['rate_revision'] != shown.price['rate_revision']

def test_pc01_variable_tariff_caps_and_precision():
    from elevenbot.pricing import manual_amount, number

    request = Request('anymodel', 'fixture/chat', 'chat', 'Fixture', 'A', {'max_tokens':4096})
    amount, _ = manual_amount(request, 'token', number('0.000000000001'), number('0.1'))
    assert amount == Decimal('409.600000000012')
    for limit in (0, 4097, True, None):
        invalid = replace(request, params={'max_tokens':limit})
        with pytest.raises(PriceUnavailable):
            manual_amount(invalid, 'token', number('1'), number('1'))
    for invalid in ('-1', 'NaN', 'Infinity', '0.0000000000001', '1000000000001'):
        with pytest.raises(PriceUnavailable):
            number(invalid)


@pytest.mark.parametrize('overlap', [False, True], ids=['sequential', 'overlapping-transactions'])
async def test_pc01_republished_tariff_one_job_one_reserve(env, confirmed_credit, monkeypatch, overlap):
    from contextlib import nullcontext
    from unittest.mock import AsyncMock

    from elevenbot.pricing import NoProviderPrice
    from test_provider_extensibility import app_with_fixture

    pool, cfg, _, user = env
    posts = []

    def generate(request):
        assert request.method == 'POST' and request.url.path == '/generate'
        posts.append(request.url.path)
        return httpx.Response(200, json={'answer':'fixture'})

    async with httpx.AsyncClient(base_url='https://fixture.invalid', transport=httpx.MockTransport(generate)) as http:
        app = app_with_fixture(pool, cfg, Bot(), http)
        app.pricing.adapters['fixture'].cost = AsyncMock(side_effect=NoProviderPrice)
        req = Request('fixture', 'fixture/chat', 'chat', 'Fixture', 'prompt')
        await confirmed_credit(pool, cfg, user, 100)
        await pool.execute("INSERT INTO approved_models VALUES('fixture',$1,'chat','Fixture')", req.model)

        publisher = Pricing(pool, app.cfg, app.pricing.adapters)

        async def publish(amount):
            await publisher.set_tariff(user, 100, req.provider, req.model, req.operation, {},
                                         basis='request', unit='darkflow_token', amount=amount, evidence='fixture')

        await publish('60')
        shown = await app.pricing.quote(user, req)
        snapshot = await pool.fetchval('SELECT price::text FROM task_price_quotes WHERE id=$1', shown.id)
        async def confirm():
            return await app.launch.confirm(user, 100, shown.id, 100, progress=lambda _: nullcontext(), background=None)

        if overlap:
            # set_tariffs calls rate inside its transaction after taking POLICY_LOCK.
            publisher_locked = asyncio.Event()
            confirmer_pid = asyncio.get_running_loop().create_future()
            read_rate = publisher.rate
            authorize = app.pricing.service.authorize

            async def wait_for_confirmer(conn, *args):
                rate = await read_rate(conn, *args)
                publisher_locked.set()
                waiter = await confirmer_pid
                assert waiter != conn.get_server_pid()
                while not await conn.fetchval(
                    'SELECT pg_backend_pid() = ANY(pg_blocking_pids($1))', waiter
                ):
                    await asyncio.sleep(0.01)
                return rate

            async def observe_confirmer(conn, *args):
                await authorize(conn, *args)
                if conn.is_in_transaction() and not confirmer_pid.done():
                    confirmer_pid.set_result(conn.get_server_pid())

            monkeypatch.setattr(publisher, 'rate', wait_for_confirmer)
            monkeypatch.setattr(app.pricing.service, 'authorize', observe_confirmer)

            async def confirm_after_lock():
                await publisher_locked.wait()
                return await confirm()

            async with asyncio.timeout(10), asyncio.TaskGroup() as group:
                group.create_task(publish('85'))
                confirmation = group.create_task(confirm_after_lock())
            accepted, ok, _ = confirmation.result()
        else:
            await publish('85')
            accepted, ok, _ = await confirm()
        assert ok and accepted.id == shown.id and accepted.price == shown.price
        with pytest.raises(Rejected):
            await app.launch.confirm(user, 100, shown.id, 101, progress=lambda _: nullcontext(), background=None)
        job = await pool.fetchrow("""SELECT d.state, q.price::text FROM task_dispatch d
            JOIN task_price_quotes q ON q.id=d.quote_id WHERE q.id=$1""", shown.id)
        assert tuple(job) == ('completed', snapshot)
        assert await pool.fetchval('SELECT count(*) FROM task_dispatch') == 1
        movements = await pool.fetch('SELECT kind,da,dr FROM ledger WHERE task_quote_id=$1 ORDER BY kind', shown.id)
        assert [tuple(row) for row in movements] == [('task_capture',0,-60), ('task_reserve',-60,60)]
        assert posts == ['/generate']
        assert (await app.svc.wallet(user))['available'] == 40
        assert (await app.pricing.quote(user, req)).price['total'] == '85'
