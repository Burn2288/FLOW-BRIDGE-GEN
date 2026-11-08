from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from elevenbot.anymodel import AnyModelProvider
from elevenbot.anymodel_pricing import AnyModelPricing
from elevenbot.anymodel_speech import SpeechPilot
from elevenbot.core import Rejected
from elevenbot.discovery import SnapshotStore, snapshot
from elevenbot.pricing import PriceUnavailable
from elevenbot.telegram import TelegramApp
from test_anymodel import routes
from test_anymodel_speech import MP3, NAME, TEXT, VOICE, VOICE_ENTRY
from test_ui import Bot, event


async def test_admin_edition_voice_manual_tariff_and_expiration(env, manual_tariff):
    pool,cfg,svc,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                anymodel_speech_live=True,anymodel_key='fixture',interaction_limit=5)
    posts=[]
    await pool.execute("INSERT INTO approved_models VALUES('anymodel',$1,'audio.speech','Voice')",VOICE)
    def respond(request):
        if request.url.path=='/v1/audio/voices':
            return httpx.Response(200,json={'data':[VOICE_ENTRY]})
        if request.url.path=='/v1/models/info':
            assert request.url.params['id']==VOICE
            return httpx.Response(404)
        assert request.url.path=='/v1/audio/speech' and request.method=='POST'
        posts.append(request)
        return httpx.Response(200,content=MP3,headers={'content-type':'audio/mpeg'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        api=AnyModelProvider(cfg.anymodel_key,client=client)
        app=TelegramApp(pool,cfg,Bot())
        app.anymodel_speech=SpeechPilot(pool,cfg,api=api)
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=api)
        guest=await svc.identity(101)
        await svc.accept(guest)
        with pytest.raises(Rejected):
            await manual_tariff(app,guest,VOICE,'audio.speech',{},provider='anymodel',external=101)
        with pytest.raises(Rejected):
            await manual_tariff(app,guest,VOICE,'audio.speech',{},provider='anymodel',external=100)
        await app.callback(user,100,'amvoices:0')
        await app.callback(user,100,routes(app.bot)[NAME])
        await app.handle(event(TEXT))
        assert 'Цена недоступна' in app.bot.sent[-1][0]
        assert 'Генерировать' not in routes(app.bot)
        assert not posts

        expiry=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        await app.handle(event(f'/tariff anymodel {VOICE} audio.speech {{}} test utf16 anymodel_balance_token 20 {expiry} fixture'))
        assert 'Предпросмотр' in app.bot.sent[-1][0]
        await app.callback(user,100,routes(app.bot)['Сохранить ставки'])
        await app.callback(user,100,'amvoices:0')
        await app.callback(user,100,routes(app.bot)[NAME])
        await app.pricing.set_rule(user,100,'anymodel',VOICE,'percent','25')
        await app.handle(event(TEXT))
        rendered=app.bot.sent[-1][0]
        assert all(part in rendered for part in ('5 ед. UTF-16','Ручная себестоимость: 100 токенов AnyModel',
                                                  'Наценка: 25','Оценка: 125'))
        cancel=routes(app.bot)['Отмена']
        stale=routes(app.bot)['Генерировать']
        await app.callback(user,100,cancel)
        with pytest.raises(Rejected):
            await app.callback(user,100,stale,request_id=2)

        await app.handle(event(TEXT))
        stale=routes(app.bot)['Генерировать']
        await pool.execute("UPDATE task_manual_tariffs SET expires_at=now()-interval '1 second'")
        with pytest.raises(PriceUnavailable):
            await app.callback(user,100,stale,request_id=3)
        assert not posts and not await pool.fetchval('SELECT count(*) FROM interaction_attempts')

        await manual_tariff(app,user,VOICE,'audio.speech',{},provider='anymodel',basis='utf16',amount='20')
        await app.handle(event(TEXT))
        confirm=routes(app.bot)['Генерировать']
        await app.callback(user,100,confirm,request_id=4)
        with pytest.raises(Rejected):
            await app.callback(user,100,confirm,request_id=5)
        assert len(posts)==1
        assert any('Генерирую' in text or 'Озвучиваю' in text for text,_ in app.bot.sent)
        assert app.bot.audio[-1][0][1].data==MP3
        await app.callback(user,100,'history:0')
        await app.callback(user,100,routes(app.bot)['Открыть работу №1'])
        assert len(app.bot.audio)==2 and app.bot.audio[-1][0][1].data==MP3


async def test_clodex_speech_uses_shared_confirmation_and_library(env, tmp_path, manual_tariff, monkeypatch):
    pool,cfg,_,user=env
    voices=tmp_path/'elevenlabs-api-voices.json'
    voices.write_text(json.dumps([{'id':'fixture-voice','name':'Voice'}]))
    catalogue=tmp_path/'catalogue.json'
    data=snapshot([{'id':'eleven-v4','title':'ElevenLabs','provider':'clodex',
                    'availability':'key_available','operations':['audio.speech']}])
    SnapshotStore(catalogue).write(data)
    cfg=replace(cfg,mode='clodex',access_mode='private',admin_ids=(100,),speech_pilot=True,
                clodex_key='fixture',clodex_model='eleven_v4',generation_enabled=True,economy_verified=True,
                catalogue_path=str(catalogue),interaction_limit=3)
    app=TelegramApp(pool,cfg,Bot())
    app.load_pilot_voices=AsyncMock()
    synth=AsyncMock(return_value=MP3)
    monkeypatch.setattr('elevenbot.providers.ClodexProvider',lambda cfg:
                        SimpleNamespace(synthesize=synth,close=AsyncMock()))
    await manual_tariff(app,user,'eleven_v4','audio.speech',{'voice':'fixture-voice'},
                        basis='utf16',amount='20')
    await app.callback(user,100,f"srun:{data['version']}:speech:0:0")
    await app.callback(user,100,routes(app.bot)['Voice'])
    await app.handle(event(TEXT))
    synth.assert_not_awaited()
    assert 'Оценка: 100' in app.bot.sent[-1][0]
    confirm=routes(app.bot)['Генерировать']
    await app.callback(user,100,confirm,request_id=2)
    with pytest.raises(Rejected):
        await app.callback(user,100,confirm,request_id=3)
    synth.assert_awaited_once_with(TEXT,'fixture-voice',1.0)
    await app.callback(user,100,'history:0')
    await app.callback(user,100,routes(app.bot)['Открыть работу №1'])
    assert len(app.bot.audio)==2 and app.bot.audio[-1][0][1].data==MP3
