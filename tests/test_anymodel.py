import json
from dataclasses import replace

import httpx
import pytest

from elevenbot import interaction, telegram
from elevenbot.anymodel_pricing import AnyModelPricing
from elevenbot.aggregate import make_snapshot
from elevenbot.anymodel import AnyModelProvider, TEST_MODEL, can_chat, model_store
from elevenbot.core import Rejected
from elevenbot.discovery import SnapshotStore
from test_ui import Bot, event


def routes(bot):
    _, keyboard = bot.sent[-1]
    return {b.text:b.callback_data for row in keyboard.inline_keyboard for b in row}


@pytest.mark.parametrize('failure', [False, True])
async def test_anymodel_menu_and_provider_routing(env,tmp_path,monkeypatch,failure,manual_tariff):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,anymodel_chat_live=True,
                anymodel_key='fixture-any',clodex_key='fixture-clodex',catalogue_path=str(tmp_path/'models.json'),
                interaction_mode='live',interaction_limit=3,interaction_pairs=(f'chat:{TEST_MODEL}',))
    ids=[f'fixture/model-{i:02}' for i in range(22)]
    records=[{'id':TEST_MODEL,'name':'DeepSeek V4 Flash Vision'},*({'id':i,'name':i} for i in ids)]
    calls=[]

    def respond(req):
        body=json.loads(req.content) if req.content else None
        calls.append((req.method,req.url.host,req.url.path,req.headers.get('Authorization'),body))
        if req.url.path=='/v1/models/info':
            assert req.url.params['id']==TEST_MODEL
            return httpx.Response(200,json={'id':TEST_MODEL,'endpoint':'/v1/chat/completions',
                'billing':{'unit':'token','coefficient':{'input':1,'output':2}}})
        if req.url.path in ('/v1/models/video','/v1/models/tts'):
            return httpx.Response(200,json={'data':[]})
        if req.method=='GET':
            return httpx.Response(200,json={'data':records})
        if req.url.host=='anymodel.org' and failure:
            raise httpx.ReadTimeout('fixture error')
        return httpx.Response(200,json={'choices':[{'message':{'content':f'Reply from {req.url.host}'}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        anymodel=AnyModelProvider(cfg.anymodel_key,client=http)
        data=await anymodel.refresh(model_store(cfg))
        assert len(data['models'])==23
        monkeypatch.setattr(telegram,'AnyModelProvider',lambda key: AnyModelProvider(key,client=http))
        execute=interaction.execute

        async def clodex(*args,**kwargs):
            return await execute(*args,**kwargs,client=http)

        monkeypatch.setattr(interaction,'execute',clodex)
        clodex_model={'id':TEST_MODEL,'title':'CLODEX fixture','provider':'clodex','operations':['chat'],
                      'availability':'key_available','protocols':['openai']}
        SnapshotStore(cfg.catalogue_path).write(make_snapshot([clodex_model],[],[
            {'provider':'clodex','scope':'key_available'},
        ]))
        bot=Bot()
        app=telegram.TelegramApp(pool,cfg,bot)
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=anymodel)
        await app.show_providers(100)
        await app.callback(user,100,routes(bot)['AnyModel'])
        assert 'Моделей: 23' in bot.sent[-1][0]
        assert 'Последнее успешное обновление' in bot.sent[-1][0]
        await app.callback(user,100,routes(bot)[telegram.OPEN_CATALOGUE])
        listed=set()
        for page in range(3):
            buttons=routes(bot)
            listed.update(v for v in buttons if v.startswith('fixture/'))
            if page<2:
                await app.callback(user,100,buttons['Далее →'])
        assert listed==set(ids)
        await app.callback(user,100,routes(bot)['← Назад'])
        await app.callback(user,100,routes(bot)['← Назад'])
        await app.callback(user,100,routes(bot)['DeepSeek V4 Flash Vision'])
        assert f'ID: {TEST_MODEL}' in bot.sent[-1][0]
        action=routes(bot)['Рассчитать стоимость']
        for restricted,external_id in ((cfg,101),(replace(cfg,anymodel_test_enabled=False),100)):
            hidden=telegram.TelegramApp(pool,restricted,Bot())
            await hidden.show_providers(external_id)
            assert 'AnyModel' not in routes(hidden.bot)
            with pytest.raises(Rejected):
                await hidden.callback(user,external_id,action)
        await app.callback(user,100,action)
        await app.handle(event('hello AnyModel'))
        assert 'ответ до 256 токенов' in bot.sent[-1][0]
        assert not any(call[0]=='POST' for call in calls)
        action=routes(bot)['Генерировать']
        await app.handle(event(callback=action).model_copy(update={'update_id':2}))
        assert ('Исход запроса неизвестен' if failure else 'Reply from anymodel.org') in bot.sent[-1][0]
        with pytest.raises(Rejected):
            await app.callback(user,100,action,request_id=3)
        assert sum(call[0]=='POST' for call in calls)==1

        version=app.catalogue_snapshot()['version']
        await app.callback(user,100,f'runmodel:{version}:0:chat')
        await manual_tariff(app,user,TEST_MODEL,'chat',{'max_tokens':512})
        await app.handle(event('hello CLODEX').model_copy(update={'update_id':4}))
        assert 'ручной тариф' in bot.sent[-1][0]
        await app.handle(event(callback=routes(bot)['Генерировать']).model_copy(update={'update_id':5}))
        assert 'Reply from clodex.xyz' in bot.sent[-1][0]
        assert [call[:4] for call in calls if call[0]=='POST']==[
            ('POST','anymodel.org','/v1/chat/completions','Bearer fixture-any'),
            ('POST','clodex.xyz','/v1/chat/completions','Bearer fixture-clodex'),
        ]
        assert all(call[4]['model']==TEST_MODEL for call in calls if call[0]=='POST')
        await app.callback(user,100,'history:0')
        works=[callback for name,callback in routes(bot).items() if name.startswith('Открыть работу')]
        assert len(works)==(1 if failure else 2)
        await app.callback(user,100,works[0])
        assert bot.sent[-1][0]=='Reply from clodex.xyz'


async def test_failed_refresh_keeps_last_authenticated_snapshot(tmp_path):
    fail=False
    def respond(req):
        if fail:return httpx.Response(503)
        if req.url.path!='/v1/models':return httpx.Response(200,json={'data':[]})
        return httpx.Response(200,json={'data':[{'id':TEST_MODEL}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        provider=AnyModelProvider('fixture',client=http)
        store=SnapshotStore(tmp_path/'anymodel.json')
        before=await provider.refresh(store)
        fail=True
        after=await provider.refresh(store)
    assert after['models']==before['models']
    assert after['version']==before['version']
    assert after['fetched_at']==before['fetched_at']
    assert after['fresh_until']==0 and after['refresh_error']=='HTTP 503'


async def test_public_fallback_is_unverified_and_does_not_use_key(tmp_path):
    def respond(req):
        if req.url.path=='/v1/models':return httpx.Response(401)
        assert 'Authorization' not in req.headers
        return httpx.Response(200,text=f'<option value="{TEST_MODEL}">Flash Vision · $0.025</option>')

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result=await AnyModelProvider('fixture',client=http).refresh(SnapshotStore(tmp_path/'anymodel.json'))
    assert result['sources'][0]['scope']=='public_only'
    assert result['refresh_error']=='HTTP 401'
    assert result['models'][0]['availability']=='public_only'
    assert not can_chat(result['models'][0],result)
