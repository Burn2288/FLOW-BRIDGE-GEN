from base64 import b64encode
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from elevenbot.anymodel import AnyModelProvider, model_store
from elevenbot.anymodel_pricing import AnyModelPricing
from elevenbot.anymodel_speech import SpeechPilot, voice_key
from elevenbot.anymodel_video import AnyModelVideoPilot, AnyModelVideoProvider
from elevenbot.core import Rejected
from elevenbot.pricing import NoProviderPrice, PriceUnavailable, Request
from elevenbot.telegram import TelegramApp
from test_anymodel import routes
from test_anymodel_speech import MP3, TEXT
from test_image_validation import encoded_image
from test_ui import Bot, event
from test_video import video


@pytest.mark.parametrize('kind,section,list_path,endpoint,expected', [
    ('image','image','/v1/models','/v1/images/generations',100),
    ('video','video','/v1/models/video','/v1/videos/generations',738),
    ('tts','speech','/v1/models/tts','/v1/audio/speech',15),
])
async def test_catalogue_new_id_launches_once(env,tmp_path,video,kind,section,list_path,endpoint,expected):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                anymodel_image_live=True,anymodel_video_live=True,anymodel_speech_live=True,
                anymodel_key='fixture',interaction_limit=5,catalogue_path=str(tmp_path/'models.json'))
    model,title=f'fixture/new-{kind}',f'New {kind}'
    params=['duration','resolution','aspect_ratio'] if kind=='video' else []
    billing={
        'image':{'unit':'image','base_tokens':100},
        'video':{'unit':'second','rates':{'720p':123}},
        'tts':{'unit':'character','base_tokens':3},
    }[kind]|{'coefficient':{'input':1,'output':1}}
    png=encoded_image('PNG')
    posts=[]
    listed=False

    def respond(req):
        path=req.url.path
        if path in ('/v1/models','/v1/models/video','/v1/models/tts'):
            rows=[{'id':model,'name':title,**({'kind':'image'} if kind=='image' else {})}]
            return httpx.Response(200,json={'data':rows if listed and path==list_path else []})
        if path=='/v1/models/info':
            assert req.url.params['id']==model
            return httpx.Response(200,json={'id':model,'endpoint':endpoint,'params':params,
                                           'billing':billing,'durations':[6]})
        if req.method=='POST':
            assert path==endpoint
            body=json.loads(req.content)
            posts.append(body)
            assert body['model']==model
            if kind=='video':
                assert body=={'model':model,'prompt':TEXT,'duration':6,'resolution':'720p','aspect_ratio':'16:9'}
                return httpx.Response(202,json={'request_id':'fixture-video'})
            if kind=='image':
                assert body=={'model':model,'prompt':TEXT,'background':True}
                return httpx.Response(200,json={'data':[{'b64_json':b64encode(png).decode()}]})
            assert body=={'model':model,'input':TEXT}
            return httpx.Response(200,content=MP3,headers={'content-type':'audio/mpeg'})
        if path=='/v1/videos/fixture-video':
            return httpx.Response(200,json={'status':'done','video':{'url':'https://invalid.example/test'}})
        assert path=='/v1/videos/fixture-video/content'
        return httpx.Response(200,content=video,headers={'content-type':'video/mp4'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        api=AnyModelVideoProvider(cfg.anymodel_key,client=http)
        bot=Bot()
        bot.send_video=AsyncMock(return_value=SimpleNamespace(message_id=55))
        app=TelegramApp(pool,cfg,bot)
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=api)
        app.anymodel_images.adapter=api
        app.anymodel_speech=SpeechPilot(pool,cfg,api=api)
        app.anymodel_video=AnyModelVideoPilot(pool,cfg,api=api)
        await api.refresh(model_store(cfg))
        await app.callback(user,100,f'amsection:{section}')
        assert title not in routes(bot)
        listed=True
        await api.refresh(model_store(cfg))
        await app.callback(user,100,f'amsection:{section}')
        await app.callback(user,100,routes(bot)[title])
        await app.callback(user,100,routes(bot)['Рассчитать стоимость'])
        if kind=='video':
            await app.callback(user,100,routes(bot)['Параметры'])
            await app.callback(user,100,routes(bot)['Секунды · 6'])
            await app.callback(user,100,routes(bot)['Разрешение · 720p'])
        await app.handle(event(TEXT))
        assert not posts
        assert str(expected) in bot.sent[-1][0]
        confirm=routes(bot)['Генерировать']
        await app.callback(user,100,confirm,request_id=2)
        with pytest.raises(Rejected):
            await app.callback(user,100,confirm,request_id=3)
        assert len(posts)==1
        if kind=='video':
            assert await app.anymodel_video.poll_one(bot)
            assert title in bot.send_video.await_args.kwargs['caption']
        elif kind=='image':
            assert await app.anymodel_images.poll_one(bot)
        await app.callback(user,100,'history:0')
        await app.callback(user,100,routes(bot)['Открыть работу №1'])
        if kind=='video':
            assert bot.send_video.await_count==2 and bot.send_video.await_args.args[1].data==video
            assert title in bot.send_video.await_args.kwargs['caption']
        elif kind=='image':
            assert len(bot.photos)==2 and bot.photos[-1][0].data==png
        else:
            assert len(bot.audio)==2 and bot.audio[-1][0][1].data==MP3


async def test_anyvoice_all_pages_refresh_and_atomic_bulk_tariff(env):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,anymodel_key='fixture')
    russian=[f'anyvoice/ru-{i}' for i in range(54)]
    english=[f'anyvoice/en-{i}' for i in range(10)]
    ids=[*russian,*english]
    new='anyvoice/'+('preset-long-'*6)
    def respond(req):
        assert req.method=='GET' and req.url.path=='/v1/audio/voices'
        assert dict(req.url.params)=={'provider':'anyvoice'}
        return httpx.Response(200,json={'data':[
            {'model':model,'name':f'Voice {i}','lang':'en' if model in english else 'ru'}
            for i,model in enumerate(ids)]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        bot=Bot()
        app=TelegramApp(pool,cfg,bot)
        app.anymodel_speech=SpeechPilot(pool,cfg,api=AnyModelProvider(cfg.anymodel_key,client=http))
        await app.callback(user,100,'amspeech:anyvoice')
        await app.callback(user,100,routes(bot)['Назначить тариф голосам'])
        seen=set()
        for page in range(7):
            current=routes(bot)
            seen.update(callback.rsplit(':',1)[-1] for callback in current.values() if callback.startswith('amvpick:'))
            if page<6:
                await app.callback(user,100,current['Далее →'])
        assert seen=={voice_key(model) for model in ids}
        ids.append(new)
        await app.callback(user,100,'amvoices:6')
        await app.callback(user,100,routes(bot)['Voice 64'])
        assert new in bot.sent[-1][0]
        await app.callback(user,100,'amvprices:0')
        await app.callback(user,100,routes(bot)['Voice 0'])
        await app.callback(user,100,'amvprices:6')
        await app.callback(user,100,routes(bot)['Voice 64'])
        await app.callback(user,100,routes(bot)['Продолжить · 2'])
        code=(await app.svc.aggregate_context(user))['tariff_code']
        expiry=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        args=[code,'test','utf16','anymodel_balance_token','10',expiry,'fixture-source']
        ids.remove(new)
        with pytest.raises(Rejected):
            await app.anyvoice_save_tariff(user,100,args)
        assert not await pool.fetchval('SELECT count(*) FROM task_manual_tariffs')
        ids.append(new)
        await app.anyvoice_save_tariff(user,100,args)
        assert all(model in bot.sent[-1][0] for model in (russian[0],new))
        assert 'Предпросмотр' in bot.sent[-1][0] and not await pool.fetchval('SELECT count(*) FROM task_manual_tariffs')
        save=routes(bot)['Сохранить ставки']
        ids.remove(new)
        with pytest.raises(Rejected):
            await app.callback(user,100,save)
        assert not await pool.fetchval('SELECT count(*) FROM task_manual_tariffs')
        ids.append(new)
        await app.callback(user,100,save)
        rows=await pool.fetch('SELECT model_id,basis,amount,evidence FROM task_manual_tariffs ORDER BY model_id')
        assert {row['model_id'] for row in rows}=={russian[0],new}
        assert all((row['basis'],row['amount'],row['evidence'])==('utf16',10,'fixture-source') for row in rows)
        with pytest.raises(Rejected):
            await app.anyvoice_save_tariff(user,100,args)
        assert not await pool.fetchval('SELECT count(*) FROM interaction_attempts')


@pytest.mark.parametrize('operation,params,basis,rate,total',[
    ('images.generate',{'n':3},'image','4.5','14'),
    ('video',{'duration':61},'second','2','122'),
    ('video',{'duration':61},'started_minute','20','40'),
    ('chat',{'max_tokens':128},'token','2:3','408'),
])
async def test_manual_units(env,manual_tariff,operation,params,basis,rate,total):
    pool,cfg,_,user=env
    app=TelegramApp(pool,replace(cfg,admin_ids=(100,)),Bot())
    class NoPrice:
        async def cost(self,request):
            raise NoProviderPrice()
    app.pricing.adapters['clodex']=NoPrice()
    request=Request('clodex','fixture/new',operation,'Fixture','A',params)
    with pytest.raises(PriceUnavailable):
        await app.pricing.quote(user,request)
    await manual_tariff(app,user,request.model,operation,params,basis=basis,amount=rate)
    quote=await app.pricing.quote(user,request)
    assert quote.price['total']==total
