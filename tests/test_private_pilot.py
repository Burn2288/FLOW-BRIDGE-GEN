from dataclasses import replace
import asyncio
import uuid
import pytest
from aiogram.types import Update
from aiohttp.test_utils import TestClient, TestServer
from elevenbot.admission import admitted
from elevenbot.config import Config
from elevenbot.core import Rejected, Service
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from test_ui import Bot
from miniapp.tests.test_miniapp import signed


def telegram_event(user, text='/start', callback=None):
    actor={'id':user,'is_bot':False,'first_name':'Fixture'}
    message={'message_id':1,'date':1700000000,'chat':{'id':user,'type':'private'},'from':actor,'text':text}
    if callback:
        return Update.model_validate({'update_id':user,'callback_query':{'id':str(user),'from':actor,'chat_instance':'fixture','message':message,'data':callback}})
    return Update.model_validate({'update_id':user,'message':message})


def test_admission_modes_and_admin_separation():
    cfg=Config(access_mode='private',admin_ids=(100,),pilot_user_ids=(101,))
    assert admitted(cfg,100) and admitted(cfg,101) and not admitted(cfg,102)
    assert not admitted(cfg,101,'max') and admitted(replace(cfg,access_mode='public'),102)
    assert 101 not in cfg.admin_ids


def test_pilot_config_validation(monkeypatch):
    monkeypatch.setattr('os.environ',{'ACCESS_MODE':'private','ADMIN_TELEGRAM_IDS':'100','PILOT_TELEGRAM_USER_IDS':'101, 102'})
    assert Config.env().pilot_user_ids==(101,102)
    monkeypatch.setenv('PILOT_TELEGRAM_USER_IDS','-1')
    with pytest.raises(ValueError):Config.env()


async def test_private_access_denied_before_registration(env):
    pool,cfg,_,_=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),pilot_user_ids=(101,))
    bot=Bot();app=TelegramApp(pool,cfg,bot)
    before={table:await pool.fetchval('SELECT count(*) FROM '+table) for table in ('users','identities','wallets','ledger','conversations')}
    await asyncio.gather(*(app.handle(telegram_event(900)) for _ in range(3)))
    await app.handle(telegram_event(901))
    await app.handle(telegram_event(900,callback='accept'))
    assert before=={table:await pool.fetchval('SELECT count(*) FROM '+table) for table in before}
    assert not await pool.fetchval("SELECT EXISTS(SELECT 1 FROM identities WHERE external_id BETWEEN 900 AND 902)")
    with pytest.raises(Rejected):await app.svc.identity(900)
    await app.handle(telegram_event(101))
    assert await pool.fetchval("SELECT EXISTS(SELECT 1 FROM identities WHERE external_id=101)")
    assert not app.has_admin_session(101)


async def test_revocation_keeps_existing_data_and_denies_miniapp(env):
    pool,cfg,_,_=env
    cfg=replace(cfg,token='fixture',access_mode='private',admin_ids=(100,),pilot_user_ids=(101,))
    service=Service(pool,cfg);user=await service.identity(101);await service.accept(user)
    async with TestClient(TestServer(create_app(pool,cfg))) as client:
        response=await client.post('/api/v1/session',json={'initData':signed('fixture',101)})
        assert response.status==200
        token=(await response.json())['token']
    before=await pool.fetchrow('SELECT * FROM wallets WHERE user_id=$1 AND mode=$2',user,'live')
    revoked=replace(cfg,pilot_user_ids=())
    async with TestClient(TestServer(create_app(pool,revoked))) as client:
        assert (await client.get('/api/v1/wallet',headers={'Authorization':'Bearer '+token})).status==403
        assert (await client.post('/api/v1/session',json={'initData':signed('fixture',101,age=1)})).status==403
    bot=Bot();app=TelegramApp(pool,revoked,bot)
    await app.handle(telegram_event(101))
    assert 'ограничен' in bot.sent[-1][0]
    assert await pool.fetchrow('SELECT * FROM wallets WHERE user_id=$1 AND mode=$2',user,'live')==before


async def test_revoked_user_payment_is_idempotent_and_job_is_preserved(env):
    pool,cfg,service,_=env
    user=await service.identity(101);await service.accept(user)
    quote,_=await service.quote(user,'fixture','demo');job=await service.confirm(user,quote)
    payment=uuid.uuid4()
    await pool.execute("INSERT INTO payments(id,user_id,amount,credits,currency,tariff,status) VALUES($1,$2,100,500,'XTR','fixture','pending')",payment,user)
    revoked=replace(cfg,access_mode='private',admin_ids=(100,),pilot_user_ids=())
    app=TelegramApp(pool,revoked,Bot())
    actor={'id':101,'is_bot':False,'first_name':'Fixture'}
    msg={'message_id':1,'date':1700000000,'chat':{'id':101,'type':'private'},'from':actor,
         'successful_payment':{'currency':'XTR','total_amount':100,'invoice_payload':str(payment),
                               'telegram_payment_charge_id':'fixture-charge','provider_payment_charge_id':'fixture'}}
    update=Update.model_validate({'update_id':999,'message':msg})
    await app.handle(update);await app.handle(update)
    assert await pool.fetchval('SELECT status FROM jobs WHERE id=$1',job)=='queued'
    assert await pool.fetchval('SELECT status FROM payments WHERE id=$1',payment)=='succeeded'
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE payment_id=$1 AND kind='payment'",payment)==1
    assert (await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user))['available']==500
