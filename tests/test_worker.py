import pytest
from elevenbot.worker import Worker
from elevenbot.providers import MockProvider,UnknownOutcome,DefinitiveFailure

async def new_job(s,u):
    q,_=await s.quote(u,'Test','demo');return await s.confirm(u,q)

async def test_A01_mock_vertical(env):
    pool,cfg,s,u=env;j=await new_job(s,u);p=MockProvider();w=Worker(pool,cfg,p)
    assert await w.run_one()
    r=await s.owned(u,j);assert r['status']=='succeeded'
    assert w.storage.path(r['storage_key']).is_file() and p.calls==1
    assert (await s.wallet(u))['available']==9996

@pytest.mark.parametrize('boundary',['before_http','after_http','after_response','after_file','before_commit'])
async def test_A11_fault_boundaries(env,boundary):
    pool,cfg,s,u=env;j=await new_job(s,u);p=MockProvider();w=Worker(pool,cfg,p)
    await w.run_one(boundary)
    async with pool.acquire() as c:await c.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=$1",j)
    await w.recover();await w.reconcile_saved();await w.run_one()
    assert (await s.owned(u,j))['status']==('succeeded' if boundary in ('after_file','before_commit') else 'uncertain')
    assert p.calls==(0 if boundary=='before_http' else 1)
    assert (await s.wallet(u))['reserved']==(0 if boundary in ('after_file','before_commit') else 4)

async def test_fencing(env):
    pool,cfg,s,u=env;j=await new_job(s,u);w=Worker(pool,cfg,MockProvider());r=await w.claim()
    async with pool.acquire() as c:await c.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=$1",j)
    assert not await s.settle(j,'release',r['fence'])
    await w.recover();assert not await w.claim()

class Broken:
    async def synthesize(self,*args):raise UnknownOutcome()
class Refused:
    async def synthesize(self,*args):raise DefinitiveFailure()

async def test_A10_timeout(env):
    pool,cfg,s,u=env;j=await new_job(s,u);w=Worker(pool,cfg,Broken());await w.run_one()
    assert (await s.owned(u,j))['status']=='uncertain';assert not await w.run_one()

async def test_A09_release(env):
    pool,cfg,s,u=env;j=await new_job(s,u);w=Worker(pool,cfg,Refused());await w.run_one()
    assert (await s.wallet(u))['available']==10000
    assert (await s.owned(u,j))['status']=='failed'

class Sender:
    def __init__(self):self.calls=0
    async def send_audio(self,*args):
        self.calls+=1
        if self.calls==1:raise TimeoutError()
        return 123

@pytest.mark.parametrize('failure', ['timeout', 'expired_lease'])
async def test_A13_delivery(env, failure):
    pool,cfg,s,u=env;j=await new_job(s,u);p=MockProvider();sender=Sender();w=Worker(pool,cfg,p,sender)
    await w.run_one()
    if failure == 'timeout':
        await w.delivery_one()
    else:
        # Telegram already accepted the upload, but sent was not committed.
        sender.calls = 1
        await pool.execute("UPDATE deliveries SET status='sending',lease_until=now()-interval '1 second' WHERE job_id=$1",j)
        await w.recover()
    assert await pool.fetchval('SELECT status FROM deliveries WHERE job_id=$1',j)=='uncertain'
    assert not await w.delivery_one()
    assert sender.calls==1
    await s.redeliver(u,j)
    assert await w.delivery_one()
    assert await pool.fetchval('SELECT status FROM deliveries WHERE job_id=$1',j)=='sent'
    assert p.calls==1 and sender.calls==2

async def test_A15_cleanup(env):
    pool,cfg,s,u=env;j=await new_job(s,u);w=Worker(pool,cfg,MockProvider());await w.run_one()
    path=w.storage.path((await s.owned(u,j))['storage_key'])
    async with pool.acquire() as c:await c.execute("UPDATE files SET expires_at=now()-interval '1 day'")
    await w.cleanup();assert not path.exists()

async def test_after_commit_no_regeneration(env):
    pool,cfg,s,u=env;j=await new_job(s,u);p=MockProvider();w=Worker(pool,cfg,p)
    await w.run_one('after_commit');await w.recover();await w.run_one()
    assert p.calls==1 and (await s.owned(u,j))['status']=='succeeded'

async def test_two_workers_one_claim(env):
    import asyncio
    pool,cfg,s,u=env;await new_job(s,u)
    a=Worker(pool,cfg,MockProvider());b=Worker(pool,cfg,MockProvider())
    results=await asyncio.gather(a.claim(),b.claim())
    assert sum(x is not None for x in results)==1
