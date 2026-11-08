import asyncio
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendAudio

from elevenbot import telegram
from elevenbot.anymodel_pricing import AnyModelPricing
from elevenbot.anymodel import AnyModelError, AnyModelProvider
from elevenbot.anymodel_speech import FISH, FISH_TITLE, SpeechPilot, validate_mp3
from elevenbot.core import Rejected
from test_anymodel import routes
from test_ui import Bot, event

VOICE = 'anyvoice/builtin-7'
NAME = 'Спокойный женский'
VOICE_ENTRY = {'model':VOICE,'name':NAME,'lang':'ru'}
TEXT = ' Я😀 '
MP3 = (Path(__file__).resolve().parents[1]/'assets'/'demo.mp3').read_bytes()


def billing(output):
    return {'unit':'character','base_tokens':50,'coefficient':{'input':1,'output':output}}


def config(cfg, *, live=True):
    return replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                   anymodel_speech_live=live,anymodel_key='fixture-any',interaction_limit=3)


@pytest.mark.parametrize('model,outcome',[
    (FISH,'success'),(VOICE,'success'),(FISH,'timeout'),(FISH,'delivery_error'),
    (FISH,'changed_rate'),(FISH,'invalid_audio'),
])
async def test_speech_confirmation_and_library(env,model,outcome):
    pool,cfg,_,user=env
    cfg=config(cfg)
    await pool.execute("INSERT INTO approved_models VALUES('anymodel',$1,'audio.speech','Voice')",VOICE)
    calls=[]
    output=1 if model==FISH else 2

    async def respond(req):
        assert req.url.host=='anymodel.org'
        assert req.headers['Authorization']=='Bearer fixture-any'
        if req.method=='GET':
            if req.url.path=='/v1/models/tts':
                return httpx.Response(200,json={'data':[{'id':FISH}]})
            if req.url.path=='/v1/audio/voices':
                assert dict(req.url.params)=={'provider':'anyvoice'}
                return httpx.Response(200,json={'data':[VOICE_ENTRY]})
            assert req.url.path=='/v1/models/info' and req.url.params['id']==model
            return httpx.Response(200,json={'id':model,'endpoint':'/v1/audio/speech','billing':billing(output)})
        assert req.method=='POST' and req.url.path=='/v1/audio/speech'
        calls.append(json.loads(req.content))
        assert await pool.fetchval('SELECT claimed AND audio IS NULL FROM anymodel_speech')
        assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1
        if outcome=='timeout':
            raise httpx.ReadTimeout('fixture')
        return httpx.Response(200,content=b'ID3' if outcome=='invalid_audio' else MP3,
                              headers={'Content-Type':'audio/mpeg'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        bot=Bot()
        app=telegram.TelegramApp(pool,cfg,bot)
        app.anymodel_speech=SpeechPilot(pool,cfg,api=AnyModelProvider(cfg.anymodel_key,client=client))
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=app.anymodel_speech.api)
        await app.callback(user,100,'am')
        await app.callback(user,100,routes(bot)['🎙 Озвучить текст'])
        await app.callback(user,100,routes(bot)[FISH_TITLE if model==FISH else 'AnyVoice'])
        if model==VOICE:
            await app.callback(user,100,routes(bot)['Выбрать голос'])
            await app.callback(user,100,routes(bot)[NAME])
        assert model in bot.sent[-1][0]
        assert (FISH_TITLE if model==FISH else NAME) in bot.sent[-1][0]
        await app.handle(event(TEXT))
        assert '5 ед. UTF-16' in bot.sent[-1][0]
        assert f'Стоимость: {250*output} токенов' in bot.sent[-1][0]
        action=routes(bot)['Генерировать']
        assert not calls
        if outcome=='changed_rate':
            output=3
            await app.callback(user,100,action,request_id=2)
            assert '750 токенов' in bot.sent[-1][0]
            assert routes(bot)['Генерировать']!=action
            assert not calls
            assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==0
            return
        if outcome=='delivery_error':
            bot.send_audio=AsyncMock(side_effect=TelegramNetworkError(SendAudio(chat_id=100,audio='fixture'),'timeout'))
        results=await asyncio.gather(
            app.callback(user,100,action,request_id=2),app.callback(user,100,action,request_id=3),
            return_exceptions=True,
        )
        assert calls==[{'model':model,'input':TEXT}], results
        assert any(isinstance(result,Rejected) for result in results)
        if outcome in ('timeout','invalid_audio'):
            assert all(isinstance(result,Rejected) for result in results)
            assert await pool.fetchval('SELECT audio FROM anymodel_speech') is None
            assert not await app.svc.history(user)
            assert not bot.audio
            return
        if outcome=='success':
            assert results.count(None)==1
            assert bot.audio[0][0][1].data==MP3
        else:
            assert any(isinstance(result,TelegramNetworkError) for result in results)
        assert await pool.fetchval('SELECT audio FROM anymodel_speech')==MP3

    restarted=telegram.TelegramApp(pool,replace(cfg,anymodel_speech_live=False),Bot())
    await restarted.callback(user,100,'history:0')
    await restarted.callback(user,100,routes(restarted.bot)['Открыть работу №1'])
    assert restarted.bot.audio[0][0][1].data==MP3
    assert 'ИИ-озвучка' in restarted.bot.audio[0][1]['caption']


async def test_voice_without_price_and_disabled_pilot(env):
    pool,cfg,_,user=env
    cfg=config(cfg)
    await pool.execute("INSERT INTO approved_models VALUES('anymodel',$1,'audio.speech','Voice')",VOICE)
    await pool.executemany("INSERT INTO approved_models VALUES('anymodel',$1,'audio.speech','Voice')",
                           [(f'anyvoice/test-{i}',) for i in range(10)])
    voices=[{'model':f'anyvoice/test-{i}','name':f'Голос {i}','lang':'ru'} for i in range(10)]+[VOICE_ENTRY]

    def respond(req):
        assert req.method=='GET'
        if req.url.path=='/v1/audio/voices':
            return httpx.Response(200,json={'data':voices})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        bot=Bot()
        app=telegram.TelegramApp(pool,cfg,bot)
        app.anymodel_speech=SpeechPilot(pool,cfg,api=AnyModelProvider(cfg.anymodel_key,client=client))
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=app.anymodel_speech.api)
        guest=await app.svc.identity(101)
        await app.svc.accept(guest)
        await app.callback(guest,101,'amvoices:0')
        assert bot.sent[-1][0]=='AnyVoice · Выберите голос'
        with pytest.raises(Rejected):
            await app.callback(guest,101,'amvprices:0')
        await app.callback(user,100,'amvoices:0')
        await app.callback(user,100,routes(bot)['Далее →'])
        origin=dict(routes(bot))
        await app.callback(user,100,routes(bot)[NAME])
        assert NAME in bot.sent[-1][0]
        assert routes(bot)=={'← К списку моделей':'amvoices:1'}
        await app.callback(user,100,routes(bot)['← К списку моделей'])
        assert routes(bot)==origin
        await app.callback(user,100,routes(bot)[NAME])
        await app.handle(event(TEXT))
        assert 'Цена недоступна' in bot.sent[-1][0]
        assert await pool.fetchval('SELECT count(*) FROM anymodel_speech')==0
        closed=telegram.TelegramApp(pool,replace(cfg,anymodel_speech_live=False),Bot())
        assert not closed.anymodel_speech.enabled(100)


def test_mp3_signature_is_not_audio():
    with pytest.raises(AnyModelError,match='MP3'):
        validate_mp3(b'ID3'+b'\x00'*16)
