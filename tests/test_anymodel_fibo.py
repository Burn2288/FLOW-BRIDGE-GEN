from base64 import b64encode
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import json

import httpx
import pytest

from elevenbot import telegram
from elevenbot.anymodel import AnyModelProvider, FIBO_MODEL, model_store
from test_anymodel import routes
from test_image_validation import encoded_image
from test_ui import Bot, event


@pytest.mark.parametrize('variant',['base64','url','broken','timeout','unsafe'])
async def test_fibo_provider_and_library(env,tmp_path,monkeypatch,variant):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,anymodel_image_live=True,
                anymodel_key='fixture-any',clodex_key='fixture-clodex',catalogue_path=str(tmp_path/'models.json'),
                interaction_limit=3)
    png=encoded_image('PNG')
    calls=[]

    async def dns(*args,**kwargs):
        return [(2,1,6,'',('93.184.216.34',443))]

    monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',dns)

    def respond(req):
        calls.append((req.method,req.url.path))
        if req.url.path=='/v1/models':
            return httpx.Response(200,json={'data':[
                {'id':FIBO_MODEL,'kind':'image'},{'id':'anymedia/fibo-lite','kind':'image'},
            ]})
        if req.url.path=='/v1/images/generations':
            assert req.url.host=='anymodel.org'
            assert req.headers['Authorization']=='Bearer fixture-any'
            assert json.loads(req.content)=={'model':FIBO_MODEL,'prompt':'Draw a blue square'}
            if variant=='timeout':
                raise httpx.ReadTimeout('fixture')
            if variant in ('url','unsafe'):
                url=('https' if variant=='url' else 'http')+'://images.example/fixture.png'
                return httpx.Response(200,json={'data':[{'url':url}]})
            image=png if variant=='base64' else png[:8]
            return httpx.Response(200,json={'data':[{'b64_json':b64encode(image).decode()}]})
        assert req.headers['Host']=='images.example'
        assert 'Authorization' not in req.headers
        return httpx.Response(200,content=png)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        await AnyModelProvider(cfg.anymodel_key,client=http).refresh(model_store(cfg))
        monkeypatch.setattr(telegram,'AnyModelProvider',lambda key: AnyModelProvider(key,client=http))
        bot=Bot()
        bot.send_photo=AsyncMock(return_value=SimpleNamespace(message_id=15))
        app=telegram.TelegramApp(pool,cfg,bot)
        await app.callback(user,100,'am')
        home=routes(bot)
        assert set(home.values())=={
            'amsection:video','amsection:image','amsection:speech','amsection:chat','amsection:tools',
            'amcat:current:0','providers',
        }
        for section in ('video','speech','chat','tools'):
            await app.callback(user,100,f'amsection:{section}')
            assert 'пока нет подключённых операций' in bot.sent[-1][0]
        await app.callback(user,100,home['🧩 Модели'])
        assert 'anymedia/fibo-lite' in routes(bot)
        await app.callback(user,100,'amsection:image')
        assert set(routes(bot))=={'FIBO 2','← AnyModel'}
        await app.callback(user,100,routes(bot)['FIBO 2'])
        assert FIBO_MODEL in bot.sent[-1][0]
        run=routes(bot)['🖼 Генерировать изображение']
        disabled=telegram.TelegramApp(pool,replace(cfg,anymodel_image_live=False),Bot())
        await disabled.callback(user,100,'amimage:detail')
        assert run not in routes(disabled.bot).values()
        await app.callback(user,100,run)
        assert 'Пришлите описание' in bot.sent[-1][0]
        prompt=event('Draw a blue square')
        await app.handle(prompt)
        if variant in ('base64','url'):
            bot.send_photo.assert_awaited_once()
            assert bot.send_photo.await_args.args[1].data==png
            await app.callback(user,100,'history:0')
            await app.callback(user,100,routes(bot)['Открыть работу №1'])
            assert bot.send_photo.await_count==2
            assert bot.send_photo.await_args.args[1].data==png
            assert await pool.fetchval('SELECT image FROM image_works')==png
        else:
            assert 'Автоповтора нет' in bot.sent[-1][0]
            await app.handle(prompt)
            assert await pool.fetchval('SELECT count(*) FROM image_works')==0
            bot.send_photo.assert_not_awaited()

    assert calls==[('GET','/v1/models'),('POST','/v1/images/generations')]+(
        [('GET','/fixture.png')] if variant=='url' else []
    )
