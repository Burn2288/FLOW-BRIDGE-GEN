import asyncio
import hashlib
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import SendPhoto
from aiohttp.test_utils import TestClient, TestServer

from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from elevenbot.core import Rejected
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed
from test_ui import Bot


async def seeded(env):
    pool,cfg,svc,user=env
    cfg=replace(cfg,interaction_limit=10,token='fixture')
    adapter=SimpleNamespace(submit_image=AsyncMock(return_value=SimpleNamespace(status=200)),
                            image_result=AsyncMock(return_value=SimpleNamespace(image=MOCK_IMAGE,filename='test.png')),
                            poll_image=AsyncMock())
    jobs=AnyModelImageJobs(pool,cfg,adapter=adapter)
    await jobs.submit(user,711,'fixture')
    row=await pool.fetchrow('SELECT id,image FROM image_works WHERE update_id=711')
    ledger=[tuple(x) for x in await pool.fetch('SELECT id,event_key,da,dr FROM ledger ORDER BY id')]
    return pool,cfg,svc,user,adapter,jobs,row,ledger


async def unchanged(pool,adapter,row,ledger):
    current=await pool.fetchrow('SELECT id,image FROM image_works WHERE update_id=711')
    assert current==row and hashlib.sha256(current['image']).digest()==hashlib.sha256(MOCK_IMAGE).digest()
    assert [tuple(x) for x in await pool.fetch('SELECT id,event_key,da,dr FROM ledger ORDER BY id')]==ledger
    assert adapter.submit_image.await_count==1 and adapter.poll_image.await_count==0
    print('image_sha256='+hashlib.sha256(current['image']).hexdigest()+' provider_posts=1 ledger_unchanged=true')


async def due(pool):
    await pool.execute("UPDATE anymodel_image_jobs SET next_at=now() WHERE update_id=711")


def rejected(message):
    return TelegramBadRequest(method=SendPhoto(chat_id=100,photo='fixture'),message=message)


async def test_definitive_rejection_is_bounded_and_library_recovers(env):
    pool,cfg,svc,user,adapter,jobs,row,ledger=await seeded(env)
    bot=Bot();bot.send_photo=AsyncMock(side_effect=rejected('bad request fixture'))
    for count in (1,2,3):
        await due(pool)
        assert await jobs.poll_one(bot)
        assert await pool.fetchval('SELECT notify_attempts FROM anymodel_image_jobs WHERE update_id=711')==count
        await unchanged(pool,adapter,row,ledger)
    await due(pool)
    assert not await jobs.poll_one(bot) and bot.send_photo.await_count==3
    bot.send_photo=AsyncMock()
    await TelegramApp(pool,cfg,bot).open_work(user,100,'image',str(row['id']))
    assert bot.send_photo.await_args.args[1].data==MOCK_IMAGE
    await unchanged(pool,adapter,row,ledger)


@pytest.mark.parametrize('failure',[TimeoutError(),asyncio.CancelledError(),
    TelegramNetworkError(method=SendPhoto(chat_id=100,photo='fixture'),message='fixture disconnect')])
async def test_unknown_or_interrupted_delivery_does_not_auto_retry(env,failure):
    pool,cfg,svc,user,adapter,jobs,row,ledger=await seeded(env)
    bot=Bot();bot.send_photo=AsyncMock(side_effect=failure);bot.send_document=AsyncMock()
    await due(pool)
    if isinstance(failure,asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):await jobs.poll_one(bot)
    else:
        assert await jobs.poll_one(bot)
    assert await pool.fetchval('SELECT notify_attempts FROM anymodel_image_jobs WHERE update_id=711')==3
    await due(pool)
    restarted=AnyModelImageJobs(pool,cfg,adapter=adapter)
    assert not await restarted.poll_one(bot) and bot.send_photo.await_count==1
    bot.send_document.assert_not_awaited()
    bot.send_photo=AsyncMock()
    await TelegramApp(pool,cfg,bot).open_work(user,100,'image',str(row['id']))
    assert bot.send_photo.await_args.args[1].data==MOCK_IMAGE
    await unchanged(pool,adapter,row,ledger)


async def test_format_rejection_falls_back_to_document(env):
    pool,cfg,svc,user,adapter,jobs,row,ledger=await seeded(env)
    bot=Bot();bot.send_photo=AsyncMock(side_effect=rejected('PHOTO_INVALID_DIMENSIONS'))
    bot.send_document=AsyncMock()
    await due(pool);assert await jobs.poll_one(bot)
    assert bot.send_photo.await_count==1 and bot.send_document.await_count==1
    assert bot.send_document.await_args.args[1].data==MOCK_IMAGE
    assert await pool.fetchval('SELECT status FROM anymodel_image_jobs WHERE update_id=711')=='delivered'
    await unchanged(pool,adapter,row,ledger)


async def test_unknown_document_outcome_does_not_retry_photo_or_document(env):
    pool,cfg,svc,user,adapter,jobs,row,ledger=await seeded(env)
    bot=Bot();bot.send_photo=AsyncMock(side_effect=rejected('PHOTO_INVALID_DIMENSIONS'))
    bot.send_document=AsyncMock(side_effect=TimeoutError())
    await due(pool);assert await jobs.poll_one(bot)
    assert await pool.fetchval('SELECT notify_attempts FROM anymodel_image_jobs WHERE update_id=711')==3
    await due(pool)
    assert not await AnyModelImageJobs(pool,cfg,adapter=adapter).poll_one(bot)
    assert bot.send_photo.await_count==1 and bot.send_document.await_count==1
    await unchanged(pool,adapter,row,ledger)


async def test_image_owner_enforced_in_service_telegram_and_http(env):
    pool,cfg,svc,user,adapter,jobs,row,ledger=await seeded(env)
    other=await svc.identity(101);await svc.accept(other)
    # Refresh baseline after legitimate creation of the second test account.
    ledger=[tuple(x) for x in await pool.fetch('SELECT id,event_key,da,dr FROM ledger ORDER BY id')]
    with pytest.raises(Rejected):await svc.image_work(other,row['id'])
    foreign_app=TelegramApp(pool,cfg,Bot())
    with pytest.raises(Rejected):await foreign_app.open_work(other,101,'image',str(row['id']))
    with pytest.raises(Rejected):await foreign_app.callback(other,101,'image:'+str(row['id']))
    async with TestClient(TestServer(create_app(pool,cfg))) as client:
        login=await client.post('/api/v1/session',json={'initData':signed('fixture',101)})
        assert login.status==200
        token=(await login.json())['token']
        response=await client.get('/api/v1/works/image/'+str(row['id']),headers={'Authorization':'Bearer '+token})
        assert response.status==404
    await unchanged(pool,adapter,row,ledger)
