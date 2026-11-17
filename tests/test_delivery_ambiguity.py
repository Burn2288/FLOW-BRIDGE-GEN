"""Accepted-but-unacknowledged media: durable stop, no regeneration."""
import asyncio
from base64 import b64encode
from dataclasses import replace
import os
import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods import SendVideo, SendPhoto
import httpx
import pytest

from elevenbot.anymodel import AnyModelProvider
from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from elevenbot.core import Rejected
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from elevenbot.video import VideoAPI, VideoPilot, MODES
from test_ui import Bot
from test_video import video  # real small ffmpeg fixture


async def ledger(pool):
    return [tuple(row) for row in await pool.fetch('SELECT id,event_key,kind,da,dr FROM ledger ORDER BY id')]


async def seeded(env, kind, media):
    pool,cfg,svc,user=env
    cfg=replace(cfg,video_pilot=True,access_mode='private',interaction_mode='live',interaction_limit=10,
                clodex_key='fixture',anymodel_key='fixture')
    calls=[]
    def respond(req):
        calls.append((req.method,req.url.path))
        if req.url.path.endswith('/estimate'):
            return httpx.Response(200,json={'success':True,'data':{'cost_usd':'0.45','model':json.loads(req.content)['model']}})
        if req.method=='POST':
            return httpx.Response(202,headers={'Retry-After':'0'},json={'id':'durable-provider-id'})
        if kind=='video':
            if req.url.path.endswith('/content'):
                return httpx.Response(200,content=media,headers={'content-type':'video/mp4'})
            return httpx.Response(200,json={'status':'done'})
        return httpx.Response(200,json={'data':[{'b64_json':b64encode(media).decode()}]})
    http=httpx.AsyncClient(transport=httpx.MockTransport(respond))
    if kind=='video':
        worker=VideoPilot(pool,cfg,api=VideoAPI('fixture',transport=httpx.MockTransport(respond)))
        job,_=await worker.quote(user,MODES['fast'][0],'fixture')
        await worker.confirm(user,job,901,MODES['fast'][0])
    else:
        worker=AnyModelImageJobs(pool,cfg,adapter=AnyModelProvider('fixture',client=http))
        job=901
        await worker.submit(user,job,'fixture')
        await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
        assert await worker.poll_one(Bot())  # persist PNG, no notification yet
    return pool,cfg,svc,user,worker,job,calls,http


async def due(pool,kind):
    await pool.execute('UPDATE video_jobs SET notify_at=now() WHERE notify_at IS NOT NULL' if kind=='video'
                       else 'UPDATE anymodel_image_jobs SET next_at=now()')


async def send(worker,kind,bot):
    return await (worker.notify_one(bot) if kind=='video' else worker.poll_one(bot))


async def fresh_process(pool,kind):
    # Actual process restart, fresh pool. Any attempted send is an assertion failure.
    schema=await pool.fetchval('SELECT current_schema()')
    code='''
import asyncio,os,asyncpg
from elevenbot.config import Config
from elevenbot.video import VideoPilot
from elevenbot.anymodel_image_jobs import AnyModelImageJobs
class NoSend:
    def __getattr__(self,name):
        async def fail(*args,**kwargs):raise AssertionError('automatic resend: '+name)
        return fail
async def main():
    pool=await asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],server_settings={'search_path':os.environ['DELIVERY_SCHEMA']})
    try:
        if os.environ['DELIVERY_KIND']=='video':
            assert not await VideoPilot(pool,Config()).notify_one(NoSend())
        else:
            assert not await AnyModelImageJobs(pool,Config()).poll_one(NoSend())
        print('fresh_process: no automatic send')
    finally:await pool.close()
asyncio.run(main())
'''
    process=await asyncio.create_subprocess_exec(sys.executable,'-c',code,
        env=os.environ|{'DELIVERY_SCHEMA':schema,'DELIVERY_KIND':kind},
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    stdout,stderr=await asyncio.wait_for(process.communicate(),30)
    assert process.returncode==0,stderr.decode()
    print(stdout.decode().strip())


@pytest.mark.parametrize('kind',['video','image'])
@pytest.mark.parametrize('outcome',['accepted_timeout','cancelled','success','rejected'])
async def test_media_delivery_restart_and_library(funded_env,video,kind,outcome):
    media=video if kind=='video' else MOCK_IMAGE
    pool,cfg,svc,user,worker,job,calls,http=await seeded(funded_env,kind,media)
    bot=Bot();accepted=[]
    other=await svc.identity(101);await svc.accept(other)
    async def deliver(*args,**kwargs):
        if outcome=='rejected':
            method=(SendVideo(chat_id=100,video='fixture') if kind=='video' else SendPhoto(chat_id=100,photo='fixture'))
            raise TelegramBadRequest(method,'definite request rejection fixture')
        accepted.append(args[1].data)
        if outcome=='accepted_timeout':raise TimeoutError('accepted; acknowledgement lost')
        if outcome=='cancelled':raise asyncio.CancelledError()
        return SimpleNamespace(message_id=88)
    bot.send_video=AsyncMock(side_effect=deliver);bot.send_photo=AsyncMock(side_effect=deliver)
    before=await ledger(pool)
    try:
        if kind=='video':
            # Polling stores bytes then calls notify_one.
            operation=worker.poll_one(bot)
        else:operation=worker.poll_one(bot)
        if outcome=='cancelled':
            with pytest.raises(asyncio.CancelledError):await operation
        else:assert await operation
        if outcome=='rejected':
            for _ in range(2):
                await due(pool,kind);assert await send(worker,kind,bot)
        await due(pool,kind)
        await fresh_process(pool,kind)
        assert not await send(worker,kind,bot)
        table='video_jobs' if kind=='video' else 'anymodel_image_jobs'
        row=await pool.fetchrow(f'SELECT status,notify_attempts FROM {table}')
        assert row['notify_attempts']==3
        assert row['status']==('succeeded' if kind=='video' else 'delivered' if outcome=='success' else 'ready')
        sends=getattr(bot,'send_'+kind if kind=='video' else 'send_photo')
        assert sends.await_count==(3 if outcome=='rejected' else 1)
        assert len(accepted)==(0 if outcome=='rejected' else 1)
        assert len([x for x in calls if x[0]=='POST' and not x[1].endswith('/estimate')])==1
        assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1
        assert await ledger(pool)==before
        work_id=job if kind=='video' else await pool.fetchval('SELECT id FROM image_works WHERE update_id=901')
        saved=(await svc.video_work(user,job) if kind=='video' else await svc.image_work(user,work_id))
        assert saved[kind]==media
        with pytest.raises(Rejected):
            if kind=='video':await svc.video_work(other,job)
            else:await svc.image_work(other,work_id)
        app=TelegramApp(pool,cfg,bot)
        method=AsyncMock();setattr(bot,'send_video' if kind=='video' else 'send_photo',method)
        await app.open_work(user,100,kind,str(work_id))
        assert method.await_args.args[1].data==media
        assert await ledger(pool)==before
        delivery=await pool.fetchrow('SELECT outcome,message_id FROM task_media_delivery WHERE kind=$1',kind)
        expected='sent' if outcome=='success' else 'rejected' if outcome=='rejected' else 'unknown'
        assert delivery['outcome']==expected
        assert delivery['message_id']==(88 if outcome=='success' else None)
        print(f'{kind} {outcome}: posts=1 quota=1 automatic_sends={sends.await_count} accepted={len(accepted)} ledger_unchanged=true library_owner=true')
    finally:await http.aclose()


@pytest.mark.parametrize('kind',['video','image'])
async def test_claim_commits_before_io_and_fences_second_worker(funded_env,video,kind):
    pool,cfg,svc,user,worker,job,calls,http=await seeded(funded_env,kind,video if kind=='video' else MOCK_IMAGE)
    if kind=='video':
        await pool.execute("UPDATE video_jobs SET status='succeeded',video=$1,expires_at=now()+interval '7 days',notify_at=now()",video)
    started,release=asyncio.Event(),asyncio.Event()
    async def held(*args,**kwargs):
        assert await pool.fetchval('SELECT outcome FROM task_media_delivery WHERE kind=$1',kind)=='unknown'
        started.set();await release.wait()
        return SimpleNamespace(message_id=77)
    bot=Bot();bot.send_video=AsyncMock(side_effect=held);bot.send_photo=AsyncMock(side_effect=held)
    task=asyncio.create_task(send(worker,kind,bot))
    try:
        await asyncio.wait_for(started.wait(),5)
        other=VideoPilot(pool,cfg,api=worker.api) if kind=='video' else AnyModelImageJobs(pool,cfg,adapter=worker.adapter)
        assert not await send(other,kind,bot)
    finally:
        release.set();await task;await http.aclose()
    assert await pool.fetchval('SELECT outcome FROM task_media_delivery WHERE kind=$1',kind)=='sent'
    assert (bot.send_video if kind=='video' else bot.send_photo).await_count==1


@pytest.mark.parametrize('kind',['video','image'])
async def test_definitive_429_respects_retry_after(funded_env,video,kind):
    pool,cfg,svc,user,worker,job,calls,http=await seeded(funded_env,kind,video if kind=='video' else MOCK_IMAGE)
    method=SendVideo(chat_id=100,video='fixture') if kind=='video' else SendPhoto(chat_id=100,photo='fixture')
    bot=Bot();failed=AsyncMock(side_effect=TelegramRetryAfter(method,'slow down',retry_after=600))
    bot.send_video=failed;bot.send_photo=failed
    try:
        assert await (worker.poll_one(bot) if kind=='video' else send(worker,kind,bot))
        query='SELECT extract(epoch FROM notify_at-now()) FROM video_jobs' if kind=='video' else 'SELECT extract(epoch FROM next_at-now()) FROM anymodel_image_jobs'
        assert 590<float(await pool.fetchval(query))<=600
        assert await pool.fetchval('SELECT outcome FROM task_media_delivery WHERE kind=$1',kind)=='rejected'
        assert not await send(worker,kind,bot)
        assert failed.await_count==1
    finally:await http.aclose()


@pytest.mark.parametrize('kind',['video','image'])
async def test_delivery_upgrade_preserves_old_unknown_attempt(funded_env,video,kind):
    from elevenbot.db import migrate
    pool,cfg,svc,user,worker,job,calls,http=await seeded(funded_env,kind,video if kind=='video' else MOCK_IMAGE)
    try:
        if kind=='video':
            # Save without notifying, as if the preceding worker was stopped.
            await pool.execute("UPDATE video_jobs SET status='succeeded',video=$1,expires_at=now()+interval '7 days',notify_at=now(),notify_attempts=1",video)
        else:await pool.execute('UPDATE anymodel_image_jobs SET notify_attempts=1')
        before=await ledger(pool)
        await pool.execute("DROP TABLE task_media_delivery; DELETE FROM schema_migrations WHERE version='041_media_delivery.sql'")
        await migrate(pool)
        first=await pool.fetch('SELECT * FROM task_media_delivery')
        assert len(first)==1 and first[0]['outcome']=='unknown'
        assert first[0]['user_id']==user
        await migrate(pool)
        assert await pool.fetch('SELECT * FROM task_media_delivery')==first
        assert await ledger(pool)==before
        # Receipt is authoritative even if a legacy counter is changed.
        await pool.execute('UPDATE video_jobs SET notify_attempts=0' if kind=='video'
                           else 'UPDATE anymodel_image_jobs SET notify_attempts=0')
        await due(pool,kind)
        await fresh_process(pool,kind)
        saved=await svc.video_work(user,job) if kind=='video' else await svc.image_work(user,await pool.fetchval('SELECT id FROM image_works'))
        assert saved[kind]==(video if kind=='video' else MOCK_IMAGE)
    finally:await http.aclose()
