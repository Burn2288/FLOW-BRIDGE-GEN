import asyncio,uuid,json
from dataclasses import replace
from elevenbot.platega import PlategaPayments,PlategaConfig,PlategaClient,PaymentUnknown,PaymentInvalid
from elevenbot.core import Service,Rejected
import pytest

REMOTE=uuid.UUID(int=302);MERCHANT=str(uuid.UUID(int=303))
class FakeClient:
    cfg=PlategaConfig(merchant=MERCHANT,secret='fixture',enabled=True,return_url='https://example.org',failed_url='https://example.org')
    def __init__(self):self.calls=0;self.order=None;self.state='CONFIRMED'
    async def create(self,p,*args):self.order=p;self.calls+=1;return REMOTE,'https://pay.platega.io/fixture'
    async def status(self,remote):return {'id':str(remote),'payload':str(self.order),'paymentDetails':{'amount':100,'currency':'RUB'},'status':self.state,'mechantId':MERCHANT}
    async def refund(self,remote):self.calls+=1;return {'transactionId':str(remote),'accepted':True}
    def authenticated(self,headers):return headers.get('X-Secret')=='fixture'

async def setup(env):
    pool,cfg,_,u=env;cfg=replace(cfg,mode='clodex',payments_enabled=True,payment_backend='platega');client=FakeClient()
    svc=PlategaPayments(pool,cfg,client);p,_=await svc.create_order(u);return svc,client,p,u

async def test_platega_duplicate_callbacks(env):
    svc,client,p,u=await setup(env)
    body=json.dumps({'id':str(REMOTE),'status':'CONFIRMED'}).encode()
    await asyncio.gather(*(svc.callback({'X-Secret':'fixture'},body) for _ in range(20)))
    assert (await svc.svc.wallet(u))['available']==10000
    async with svc.pool.acquire() as c:assert await c.fetchval("SELECT count(*) FROM ledger WHERE kind='payment'")==1

async def test_platega_server_state_overrides_stale_callback(env):
    svc,client,p,u=await setup(env);client.state='PENDING'
    await svc.callback({'X-Secret':'fixture'},json.dumps({'id':str(REMOTE),'status':'CONFIRMED'}))
    assert (await svc.svc.wallet(u))['available']==0
    client.state='CONFIRMED';await svc.sync(REMOTE);client.state='DISPUTED';await svc.sync(REMOTE)
    client.state='CONFIRMED';await svc.sync(REMOTE)
    async with svc.pool.acquire() as c:assert await c.fetchval("SELECT count(*) FROM ledger WHERE kind='payment'")==1

async def test_platega_callback_wrong_payload(env):
    svc,client,p,u=await setup(env);client.order=uuid.uuid4()
    with pytest.raises(PaymentInvalid):await svc.sync(REMOTE)
    assert (await svc.svc.wallet(u))['available']==0

async def test_platega_refund_completion_and_duplicate(env):
    svc,client,p,u=await setup(env);await svc.sync(REMOTE)
    await svc.refund(p)
    with pytest.raises(Rejected):await svc.refund(p)
    assert (await svc.svc.wallet(u))['reserved']==10000
    client.state='CHARGEBACKED';await svc.sync(REMOTE);await svc.sync(REMOTE)
    assert (await svc.svc.wallet(u))['reserved']==0
    async with svc.pool.acquire() as c:
        assert await c.fetchval("SELECT count(*) FROM ledger WHERE kind='refund'")==1
        assert not await c.fetchval('SELECT halted FROM settings WHERE id=1')

async def test_platega_create_timeout_persisted(env):
    pool,cfg,_,u=env;cfg=replace(cfg,mode='clodex',payments_enabled=True,payment_backend='platega');client=FakeClient()
    async def fail(*args):client.calls+=1;raise PaymentUnknown()
    client.create=fail;svc=PlategaPayments(pool,cfg,client)
    with pytest.raises(PaymentUnknown):await svc.create_order(u)
    async with pool.acquire() as c:assert await c.fetchval("SELECT count(*) FROM payments WHERE creation_state='uncertain'")==1
    assert client.calls==1

async def test_A13_manual_redelivery_after_retry_exhaustion(env):
    from elevenbot.worker import Worker
    from elevenbot.providers import MockProvider
    pool,cfg,s,u=env;q,_=await s.quote(u,'Hello','demo');j=await s.confirm(u,q)
    await Worker(pool,cfg,MockProvider()).run_one()
    async with pool.acquire() as c:await c.execute("UPDATE deliveries SET status='expired',attempts=8 WHERE job_id=$1",j)
    await s.redeliver(u,j)
    async with pool.acquire() as c:
        r=await c.fetchrow('SELECT * FROM deliveries WHERE job_id=$1',j);assert r['status']=='pending' and r['attempts']==0
