import asyncio
from base64 import b64encode
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from elevenbot import telegram
from elevenbot.anymodel_pricing import AnyModelPricing
from elevenbot.anymodel_video import AnyModelVideoPilot, AnyModelVideoProvider, MODEL, TITLE, validate_mp4
from elevenbot.core import Rejected
from elevenbot.video import InvalidVideoError
from test_anymodel import routes
from test_ui import Bot, event
from test_video import video


TARIFF={
    'id':MODEL,'endpoint':'/v1/videos/generations','params':['duration','resolution','aspect_ratio'],
    'billing':{'unit':'second','rates':{'480p':800000},'coefficient':{'input':1,'output':1}},
}

POLL_PROCESS=r"""
import asyncio
from base64 import b64decode
from dataclasses import replace
import os

import asyncpg
import httpx

from elevenbot.anymodel_video import AnyModelVideoPilot,AnyModelVideoProvider
from elevenbot.config import Config
from elevenbot.progress import TaskProgress

calls=[]
def respond(req):
    assert req.method=='GET' and req.url.host=='anymodel.org'
    assert req.headers['Authorization']=='Bearer fixture-any'
    assert req.headers['x-9router-connection-id']=='fixture-ticket'
    calls.append(req.url.path)
    if len(calls)==1:
        raise httpx.ReadTimeout('fixture')
    if req.url.path.endswith('/content'):
        return httpx.Response(200,content=b64decode(os.environ['VIDEO_BYTES']),headers={'Content-Type':'video/mp4'})
    return httpx.Response(200,json={'status':'done','video':{'url':'https://untrusted.example/unused'}})

class Bot:
    async def edit_message_text(self,text,*,chat_id,message_id):
        assert chat_id==100 and message_id==int(os.environ['VIDEO_STATUS_MESSAGE'])
        assert text.startswith('✅ Grok Imagine Video 1.5')
        print('telegram_status_completed')

    async def send_video(self,chat,file,**kwargs):
        assert chat==100 and file.data==b64decode(os.environ['VIDEO_BYTES'])
        print('telegram_delivery_confirmed')

async def main():
    async with asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],min_size=1,
                                   server_settings={'search_path':os.environ['VIDEO_SCHEMA']}) as pool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            cfg=replace(Config(),anymodel_key='fixture-any',anymodel_video_live=False)
            pilot=AnyModelVideoPilot(pool,cfg,api=AnyModelVideoProvider(cfg.anymodel_key,client=http))
            assert await pilot.poll_one(Bot())
            assert await pool.fetchval("SELECT next_poll_at>now() AND status='polling' FROM video_jobs")
            assert not await pilot.poll_one(Bot())
            await pool.execute('UPDATE video_jobs SET next_poll_at=now()')
            assert await pilot.poll_one(Bot())
            assert calls==['/v1/videos/fixture-job','/v1/videos/fixture-job','/v1/videos/fixture-job/content']
            assert await pool.fetchval("SELECT status='succeeded' AND notify_at IS NULL FROM video_jobs")
            await TaskProgress(Bot(),pool).refresh()
            assert not await pool.fetchval('SELECT EXISTS(SELECT 1 FROM task_progress)')

asyncio.run(main())
"""


@pytest.mark.parametrize('lose_response',[False,True])
async def test_anymodel_video_confirmation_and_restart(funded_env,video,lose_response):
    pool,cfg,_,user=funded_env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                anymodel_video_live=True,anymodel_key='fixture-any',interaction_limit=3)
    calls=[]

    async def respond(req):
        assert req.url.host=='anymodel.org'
        assert req.headers['Authorization']=='Bearer fixture-any'
        if req.method=='GET':
            assert req.url.path=='/v1/models/info' and req.url.params['id']==MODEL
            return httpx.Response(200,json=TARIFF)
        assert req.url.path=='/v1/videos/generations'
        calls.append(req.url.path)
        row=await pool.fetchrow('SELECT idempotency_key,status FROM video_jobs')
        assert row['status']=='submitting'
        assert str(row['idempotency_key'])==req.headers['Idempotency-Key']
        assert json.loads(req.content)=={
            'model':MODEL,'prompt':'Blue square','duration':4,'resolution':'480p','aspect_ratio':'16:9',
        }
        if lose_response:
            raise httpx.ReadTimeout('fixture')
        return httpx.Response(202,json={'request_id':'fixture-job'},headers={'x-9router-connection-id':'fixture-ticket'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        api=AnyModelVideoProvider(cfg.anymodel_key,client=http)
        bot=Bot()
        app=telegram.TelegramApp(pool,cfg,bot)
        app.anymodel_video=AnyModelVideoPilot(pool,cfg,api=api)
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=api)
        await app.callback(user,100,'am')
        await app.callback(user,100,routes(bot)['🎬 Генерировать видео'])
        await app.callback(user,100,routes(bot)[TITLE])
        assert not calls
        await app.callback(user,100,routes(bot)['🎬 Генерировать видео'])
        await app.handle(event('Blue square'))
        assert '4 с · 480p · 16:9' in bot.sent[-1][0] and '3\u202f200\u202f000' in bot.sent[-1][0]
        assert not calls
        confirmation=routes(bot)['Генерировать']
        results=await asyncio.gather(
            app.callback(user,100,confirmation,request_id=2),
            app.callback(user,100,confirmation,request_id=3),return_exceptions=True,
        )
        assert any(isinstance(r,Rejected) for r in results)
        assert calls==['/v1/videos/generations']
        assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1
        status_message=await pool.fetchval('SELECT message_id FROM task_progress')
        assert status_message and '⏳ Grok Imagine Video 1.5' in bot.sent[-1][0]
        await app.callback(user,100,'home')
        assert status_message not in bot.deleted
        if lose_response:
            assert all(isinstance(r,Rejected) for r in results)
            assert await pool.fetchval("SELECT status='uncertain' AND provider_id IS NULL FROM video_jobs")
            assert not await app.anymodel_video.poll_one(bot)
            await app.progress.refresh()
            assert 'Исход запроса неизвестен' in bot.sent[-1][0]
            return
        assert results.count(None)==1
        assert await pool.fetchval("""
            SELECT provider='anymodel' AND provider_id='fixture-job' AND connection_id='fixture-ticket'
            FROM video_jobs
        """)

    proc=await asyncio.create_subprocess_exec(sys.executable,'-c',POLL_PROCESS,env=os.environ|{
        'VIDEO_SCHEMA':await pool.fetchval('SELECT current_schema()'),
        'VIDEO_BYTES':b64encode(video).decode(),
        'VIDEO_STATUS_MESSAGE':str(status_message),
        'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src'),
    },stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        async with asyncio.timeout(30):
            stdout,stderr=await proc.communicate()
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
    assert proc.returncode==0,stderr.decode()
    assert b'telegram_delivery_confirmed' in stdout and b'video_poll_failed' in stdout
    assert b'telegram_status_completed' in stdout
    assert b'fixture-any' not in stdout and b'fixture-ticket' not in stdout
    bot=Bot()
    bot.send_video=AsyncMock(return_value=SimpleNamespace(message_id=15))
    restarted=telegram.TelegramApp(pool,cfg,bot)
    await restarted.callback(user,100,'history:0')
    await restarted.callback(user,100,routes(bot)['Открыть работу №1'])
    assert bot.send_video.await_args.args[1].data==video
    assert await pool.fetchval('SELECT video FROM video_jobs')==video


async def test_anymodel_video_missing_price_keeps_launch_closed(env):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                anymodel_video_live=True,anymodel_key='fixture-any',interaction_limit=3)
    def respond(req):
        assert req.method=='GET'
        return httpx.Response(200,json={**TARIFF,'billing':{}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        app=telegram.TelegramApp(pool,cfg,Bot())
        app.anymodel_video=AnyModelVideoPilot(pool,cfg,api=AnyModelVideoProvider(cfg.anymodel_key,client=http))
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=app.anymodel_video.api)
        await app.callback(user,100,'amvideo:run')
        await app.handle(event('Video'))
        assert 'Цена недоступна' in app.bot.sent[-1][0]
        guest=await app.svc.identity(101)
        await app.svc.accept(guest)
        await app.callback(guest,101,'amvideo:detail')
        assert 'Агрегатор 2' in app.bot.sent[-1][0]


def test_rejects_mp4_signature_only():
    with pytest.raises(InvalidVideoError):
        validate_mp4(b'\x00\x00\x00\x10ftypisom\x00\x00\x00\x00')
