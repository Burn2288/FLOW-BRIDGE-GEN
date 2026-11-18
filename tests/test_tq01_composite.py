"""Cross-candidate regression: private admission plus saved-image recovery."""
import hashlib
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from elevenbot.core import Rejected
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from test_private_pilot import telegram_event
from test_ui import Bot


async def test_private_image_delivery_recovery_keeps_ledger_and_admission(env):
    pool,cfg,_,owner=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),pilot_user_ids=(101,),interaction_limit=10)
    adapter=SimpleNamespace(submit_image=AsyncMock(return_value=SimpleNamespace(status=200)),
                            image_result=AsyncMock(return_value=SimpleNamespace(image=MOCK_IMAGE,filename='test.png')),
                            poll_image=AsyncMock())
    jobs=AnyModelImageJobs(pool,cfg,adapter=adapter)
    ledger=await pool.fetch('SELECT id,event_key,kind,da,dr FROM ledger ORDER BY id')
    await jobs.submit(owner,771,'fixture')
    work=await pool.fetchrow('SELECT id,image FROM image_works WHERE update_id=771')
    bot=Bot();bot.send_photo=AsyncMock(side_effect=TimeoutError())
    await pool.execute('UPDATE anymodel_image_jobs SET next_at=now() WHERE update_id=771')
    assert await jobs.poll_one(bot)
    assert await pool.fetchval('SELECT notify_attempts FROM anymodel_image_jobs WHERE update_id=771')==3
    await pool.execute('UPDATE anymodel_image_jobs SET next_at=now() WHERE update_id=771')
    assert not await AnyModelImageJobs(pool,cfg,adapter=adapter).poll_one(bot)
    bot.send_photo=AsyncMock()
    app=TelegramApp(pool,cfg,bot)
    await app.open_work(owner,100,'image',str(work['id']))
    assert bot.send_photo.await_args.args[1].data==MOCK_IMAGE
    tester=await app.svc.identity(101);await app.svc.accept(tester)
    with pytest.raises(Rejected):await app.callback(tester,101,'image:'+str(work['id']))
    await app.handle(telegram_event(102))
    assert not await pool.fetchval("SELECT EXISTS(SELECT 1 FROM identities WHERE external_id=102)")
    assert await pool.fetch('SELECT id,event_key,kind,da,dr FROM ledger ORDER BY id')==ledger
    assert adapter.submit_image.await_count==1 and adapter.poll_image.await_count==0
    assert hashlib.sha256(work['image']).digest()==hashlib.sha256(MOCK_IMAGE).digest()
    print('TQ01 combined: admission=pass recovery=pass ledger=unchanged mock_submit=1 image_sha256='+hashlib.sha256(work['image']).hexdigest())
