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


async def test_new_model_from_catalogue_and_unknown_billing(env, tmp_path, monkeypatch):
    pool, cfg, _, user = env
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
