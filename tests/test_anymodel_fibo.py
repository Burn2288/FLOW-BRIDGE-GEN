from base64 import b64encode
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx
import pytest

from elevenbot import telegram
from elevenbot.anymodel import AnyModelProvider, FIBO_MODEL, model_store
from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from test_anymodel import routes
from test_image_validation import encoded_image
from test_ui import Bot, event


@pytest.mark.parametrize('variant',['base64','url','broken','timeout','connect','unsafe'])
async def test_fibo_provider_and_library(env,tmp_path,monkeypatch,capsys,variant):
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
            assert json.loads(req.content)=={'model':FIBO_MODEL,'prompt':'Draw a blue square','background':True}
            if variant=='timeout':
                raise httpx.ReadTimeout('fixture')
            if variant=='connect':
                raise httpx.ConnectError('fixture')
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
        for section in ('chat','tools'):
            await app.callback(user,100,f'amsection:{section}')
            assert 'пока нет подключённых операций' in bot.sent[-1][0]
        await app.callback(user,100,home[telegram.OPEN_CATALOGUE])
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
            jobs=AnyModelImageJobs(pool,cfg,adapter=AnyModelProvider(cfg.anymodel_key,client=http))
            assert await jobs.poll_one(bot)
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
            expected='unknown' if variant in ('timeout','connect') else 'failed'
            assert await pool.fetchval('SELECT status FROM anymodel_image_jobs')==expected
            if variant in ('timeout','connect'):
                log=capsys.readouterr().out
                assert ('response_timeout' if variant=='timeout' else 'connect_error') in log
                assert 'Draw a blue square' not in log and 'fixture-any' not in log
            assert await pool.fetchval('SELECT count(*) FROM image_works')==0
            bot.send_photo.assert_not_awaited()

    assert calls==[('GET','/v1/models'),('POST','/v1/images/generations')]+(
        [('GET','/fixture.png')] if variant=='url' else []
    )

POLL_AFTER_RESTART = r"""
import asyncio
from base64 import b64decode
import hashlib
import os

import asyncpg
import httpx

from elevenbot.anymodel import AnyModelProvider
from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from elevenbot.config import Config

calls=[]

def respond(req):
    assert req.method=='GET'
    assert req.url.path=='/v1/images/generations/fixture-job'
    assert req.headers['Authorization']=='Bearer fixture-any'
    calls.append(req.url.path)
    if len(calls)==1:
        return httpx.Response(202,headers={'Retry-After':'12'},json={'id':'fixture-job','status':'in_progress'})
    if len(calls)==2:
        raise httpx.ReadTimeout('fixture')
    return httpx.Response(200,json={'data':[{'b64_json':os.environ['FIBO_PNG']}]})

class Bot:
    async def send_photo(self,external,media,**kwargs):
        assert external==100
        assert media.data==b64decode(os.environ['FIBO_PNG'])
        print('telegram_sha256='+hashlib.sha256(media.data).hexdigest())

async def main():
    async with asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],min_size=1,
                                   server_settings={'search_path':os.environ['FIBO_SCHEMA']}) as pool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            jobs=AnyModelImageJobs(pool,Config(),adapter=AnyModelProvider('fixture-any',client=http))
            assert not await jobs.poll_one(Bot())
            await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
            assert await jobs.poll_one(Bot())
            assert await pool.fetchval('SELECT next_at>now()+interval \'10 seconds\' FROM anymodel_image_jobs')
            assert not await jobs.poll_one(Bot())
            await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
            assert await jobs.poll_one(Bot())
            assert await pool.fetchval("SELECT status='pending' AND provider_id='fixture-job' FROM anymodel_image_jobs")
            await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
            assert await jobs.poll_one(Bot())
            assert await jobs.poll_one(Bot())
            assert await pool.fetchval("SELECT status='delivered' FROM anymodel_image_jobs")
            assert len(calls)==3

asyncio.run(main())
"""


async def test_fibo_202_resumes_in_fresh_process(env,tmp_path,monkeypatch):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,anymodel_image_live=True,
                anymodel_key='fixture-any',catalogue_path=str(tmp_path/'models.json'),interaction_limit=3)
    png=encoded_image('PNG')
    requests=[]

    def respond(req):
        requests.append((req.method,req.url.path))
        if req.method=='GET':
            return httpx.Response(200,json={'data':[{'id':FIBO_MODEL,'kind':'image'}]})
        assert json.loads(req.content)=={'model':FIBO_MODEL,'prompt':'Blue square','background':True}
        return httpx.Response(202,headers={'Retry-After':'120','Location':'https://untrusted.example/ignore'},
                              json={'id':'fixture-job','status':'queued'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        adapter=AnyModelProvider(cfg.anymodel_key,client=http)
        await adapter.refresh(model_store(cfg))
        monkeypatch.setattr(telegram,'AnyModelProvider',lambda key: adapter)
        before=Bot()
        app=telegram.TelegramApp(pool,cfg,before)
        await app.callback(user,100,'am')
        await app.callback(user,100,routes(before)['🖼 Генерировать изображение'])
        await app.callback(user,100,routes(before)['FIBO 2'])
        await app.callback(user,100,routes(before)['🖼 Генерировать изображение'])
        await app.handle(event('Blue square'))
        assert 'запрос принят' in before.sent[-1][0]
    assert requests==[('GET','/v1/models'),('POST','/v1/images/generations')]
    assert await pool.fetchval("""
        SELECT status='pending' AND provider_id='fixture-job' AND next_at>now()+interval '110 seconds'
        FROM anymodel_image_jobs
        """)
    assert not await pool.fetchval('SELECT count(*) FROM image_works')

    schema=await pool.fetchval('SELECT current_schema()')
    process=await asyncio.create_subprocess_exec(
        sys.executable,'-c',POLL_AFTER_RESTART,
        env=os.environ|{
            'FIBO_SCHEMA':schema,
            'FIBO_PNG':b64encode(png).decode(),
            'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src'),
        },
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(30):
            stdout,stderr=await process.communicate()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode==0, stderr.decode()
    assert b'anymodel_image_poll_failed' in stdout and b'response_timeout' in stdout
    assert b'telegram_sha256=' in stdout
    assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1

    bot=Bot()
    bot.send_photo=AsyncMock(return_value=SimpleNamespace(message_id=15))
    restarted=telegram.TelegramApp(pool,cfg,bot)
    await restarted.callback(user,100,'history:0')
    await restarted.callback(user,100,routes(bot)['Открыть работу №1'])
    assert bot.send_photo.await_args.args[1].data==png
    assert await pool.fetchval('SELECT image FROM image_works')==png
