from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from elevenbot.anymodel import AnyModelProvider
from elevenbot.anymodel_pricing import AnyModelPricing
from elevenbot.anymodel_speech import SpeechPilot
from elevenbot.core import Rejected, uid
from elevenbot.discovery import SnapshotStore, snapshot
from elevenbot.pricing import PriceUnavailable, Request
from elevenbot.telegram import TelegramApp
from test_anymodel import routes
from test_anymodel_speech import MP3, TEXT
from test_ui import Bot, event


@pytest.mark.parametrize('price_endpoint',['models/info','audio/voices'])
async def test_tariff_catalogue_custom_voice_and_api_priority(env,price_endpoint):
    pool,cfg,svc,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                anymodel_speech_live=True,anymodel_key='fixture',interaction_limit=4)
    bot=Bot()
    custom='anyvoice/custom-new'
    current=[{'model':f'anyvoice/builtin-{n}','name':f'Voice {n}','lang':'ru'} for n in range(54)]
    billing={'unit':'character','base_tokens':30,'coefficient':{'input':1,'output':1}}
    published=False
    posts=[]

    def respond(req):
        if req.url.path=='/v1/audio/voices':
            assert req.method=='GET' and dict(req.url.params)=={'provider':'anyvoice'}
            rows=[row|{'billing':billing} if row['model']==custom and published and
                  price_endpoint=='audio/voices' else row for row in current]
            return httpx.Response(200,json={'data':rows})
        if req.url.path=='/v1/models/info':
            assert req.url.params['id']==custom
            if published and price_endpoint=='models/info':
                return httpx.Response(200,json={'id':custom,'endpoint':'/v1/audio/speech','billing':billing})
            return httpx.Response(404)
        assert req.method=='POST' and req.url.path=='/v1/audio/speech'
        posts.append(json.loads(req.content))
        return httpx.Response(200,content=MP3,headers={'content-type':'audio/mpeg'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        api=AnyModelProvider(cfg.anymodel_key,client=http)
        app=TelegramApp(pool,cfg,bot)
        app.anymodel_speech=SpeechPilot(pool,cfg,api=api)
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=api)
        guest=await svc.identity(101)
        await svc.accept(guest)
        with pytest.raises(Rejected):
            await app.callback(guest,101,'tariffs')
        with pytest.raises(Rejected):
            await app.callback(guest,100,'tariffs')
        await app.show_providers(100)
        await app.callback(user,100,routes(bot)['Тарифы моделей'])
        assert {'AnyModel','AnyVoice','CLODEX'}.issubset(routes(bot))
        await app.callback(user,100,routes(bot)['AnyVoice'])
        assert '(54)' in bot.sent[-1][0]
        for _ in range(5):
            await app.callback(user,100,routes(bot)['Далее →'])
        assert 'Custom' not in routes(bot)
        current.append({'model':custom,'name':'Custom','lang':'ru','custom':True})
        await app.callback(user,100,routes(bot)['↻ Обновить каталог'])
        await app.callback(user,100,routes(bot)['Custom'])
        await app.callback(user,100,routes(bot)['Озвучка'])
        assert 'Цена недоступна' in bot.sent[-1][0]

        await app.callback(user,100,routes(bot)['Временная тестовая ставка'])
        code=(await svc.aggregate_context(user))['tariff_admin']['code']
        with pytest.raises(Rejected,match='нужен срок'):
            await app.price_admin(user,100,'/tariff_set',[code,'utf16','anymodel_balance_token','10','fixture'])
        assert not await pool.fetchval('SELECT count(*) FROM task_manual_tariffs')
        expiry=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        await app.price_admin(user,100,'/tariff_set',[code,'utf16','anymodel_balance_token','10',expiry,'fixture'])
        row=await pool.fetchrow('SELECT * FROM task_manual_tariffs')
        assert row['temporary'] and row['expires_at'] and row['verified_at'] and row['admin_id']==user
        await pool.execute("UPDATE task_manual_tariffs SET expires_at=now()-interval '1 second'")
        await app.callback(user,100,routes(bot)['↻ Проверить источник'])
        assert 'Цена недоступна' in bot.sent[-1][0] and 'истекла' in bot.sent[-1][0]

        await app.callback(user,100,routes(bot)['Задать ручную ставку'])
        code=(await svc.aggregate_context(user))['tariff_admin']['code']
        with pytest.raises(Rejected,match='Studio'):
            await app.price_admin(user,100,'/tariff_set',[code,'utf16','anymodel_balance_token','20','fixture'])
        await app.price_admin(user,100,'/tariff_set',[code,'utf16','anymodel_balance_token','20','studio:fixture'])
        row=await pool.fetchrow('SELECT * FROM task_manual_tariffs')
        assert row['expires_at'] is None and row['enabled'] and not row['temporary']
        assert 'без срока' in bot.sent[-1][0] and 'Действующий источник: Ручная ставка' in bot.sent[-1][0]
        await app.callback(user,100,routes(bot)['Отключить ручную ставку'])
        assert 'отключена' in bot.sent[-1][0] and 'Цена недоступна' in bot.sent[-1][0]
        await app.callback(user,100,routes(bot)['Задать ручную ставку'])
        code=(await svc.aggregate_context(user))['tariff_admin']['code']
        await app.price_admin(user,100,'/tariff_set',[code,'utf16','anymodel_balance_token','20','support:fixture'])

        await app.callback(user,100,'amvoices:5')
        await app.callback(user,100,routes(bot)['Custom'])
        await app.pricing.set_rule(user,100,'anymodel',custom,'percent','25')
        await app.handle(event(TEXT))
        assert 'Оценка: 125' in bot.sent[-1][0]
        old=routes(bot)['Генерировать']
        assert not posts
        published=True
        await app.callback(user,100,old,request_id=2)
        assert not posts and 'Стоимость: 188' in bot.sent[-1][0]
        fresh=routes(bot)['Генерировать']
        with pytest.raises(Rejected):
            await app.callback(user,100,old,request_id=3)
        await app.callback(user,100,fresh,request_id=4)
        with pytest.raises(Rejected):
            await app.callback(user,100,fresh,request_id=5)
        assert posts==[{'model':custom,'input':TEXT}]
        accepted=await pool.fetchrow('SELECT price,state FROM task_price_quotes WHERE id=$1',uid(fresh.split(':')[1]))
        price=json.loads(accepted['price'])
        assert price['source'].startswith('/v1/'+price_endpoint) and price['total']=='188'
        assert accepted['state']=='accepted'
        assert not await pool.fetchval('SELECT count(*) FROM task_price_accounting')


async def test_tariff_catalogue_exact_mode_and_disable(env,tmp_path):
    pool,cfg,svc,user=env
    path=tmp_path/'catalogue.json'
    model='fixture/image'
    SnapshotStore(path).write(snapshot([{
        'id':model,'title':'Fixture image','provider':'clodex','availability':'key_available',
        'operations':['images.generate','chat'],
    }]))
    app=TelegramApp(pool,replace(cfg,access_mode='private',admin_ids=(100,),catalogue_path=str(path)),Bot())
    await app.callback(user,100,'tariffs:clodex:0')
    await app.callback(user,100,routes(app.bot)['Fixture image'])
    assert {'Изображение','Чат'}.issubset(routes(app.bot))
    await app.callback(user,100,routes(app.bot)['Изображение'])
    code=(await svc.aggregate_context(user))['tariff_admin']['code']
    await app.price_admin(user,100,'/tariff_scope',[code,'{"n": 1, "quality": "high"}'])
    await app.callback(user,100,routes(app.bot)['Задать ручную ставку'])
    code=(await svc.aggregate_context(user))['tariff_admin']['code']
    await app.price_admin(user,100,'/tariff_set',[code,'image','anymodel_balance_token','21','fixture-source'])
    req=Request('clodex',model,'images.generate','Fixture image','Prompt',{'n':1,'quality':'high'})
    assert (await app.pricing.quote(user,req)).price['total']=='21'
    with pytest.raises(PriceUnavailable):
        await app.pricing.quote(user,replace(req,params={'n':1}))
    await app.callback(user,100,routes(app.bot)['Отключить ручную ставку'])
    assert not await pool.fetchval('SELECT enabled FROM task_manual_tariffs')
    with pytest.raises(PriceUnavailable):
        await app.pricing.quote(user,req)
