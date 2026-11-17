import asyncio,uuid
from dataclasses import replace
import pytest
from elevenbot.core import Service,Rejected
from elevenbot.worker import Worker
from elevenbot.providers import MockProvider

async def test_A02_twenty_confirmations(env):
    pool,cfg,s,u=env;q,_=await s.quote(u,'Hello','demo')
    ids=await asyncio.gather(*(s.confirm(u,q) for _ in range(20)))
    assert len(set(ids))==1
    async with pool.acquire() as c:
        assert await c.fetchval("SELECT count(*) FROM ledger WHERE kind='reserve'")==1
    assert (await s.wallet(u))['reserved']==5

async def test_A03_insufficient(env):
    pool,cfg,s,u=env;v=await s.identity(101)
    async with pool.acquire() as c:await c.execute("UPDATE identities SET accepted_at=now(),terms_version='1' WHERE user_id=$1",v)
    q,_=await s.quote(v,'Hello','demo')
    with pytest.raises(Rejected):await s.confirm(v,q)
    async with pool.acquire() as c:assert await c.fetchval('SELECT count(*) FROM jobs')==0

async def test_A04_two_quotes(env):
    _,_,s,u=env;a,_=await s.quote(u,'One','demo');b,_=await s.quote(u,'Two','demo')
    r=await asyncio.gather(s.confirm(u,a),s.confirm(u,b),return_exceptions=True)
    assert sum(isinstance(x,uuid.UUID) for x in r)==1
    assert sum(isinstance(x,Rejected) for x in r)==1

async def test_A07_ownership(env):
    _,_,s,u=env;q,_=await s.quote(u,'Private','demo');j=await s.confirm(u,q)
    v=await s.identity(102);await s.accept(v)
    for op in [s.owned(v,j),s.cancel(v,j),s.redeliver(v,j),s.confirm(v,q)]:
        with pytest.raises(Rejected):await op

async def test_A14_settlement_race(env):
    pool,cfg,s,u=env;q,_=await s.quote(u,'Hello','demo');j=await s.confirm(u,q)
    artifact={'key':'fake','sha256':'fake','size':1}
    await asyncio.gather(s.settle(j,'capture',storage=artifact),s.settle(j,'release'))
    async with pool.acquire() as c:
        assert await c.fetchval("SELECT count(*) FROM ledger WHERE kind IN ('capture','release')")==1
    w=await s.wallet(u);assert w['reserved']==0 and w['available'] in (9995,10000)

async def paid_service(env):
    pool,cfg,_,u=env
    s=Service(pool,replace(cfg,mode='clodex',payments_enabled=True,payment_backend='stars'))
    return s,u

async def test_A05_payment_duplicates(env):
    s,u=await paid_service(env);p=await s.order(u)
    outcomes=await asyncio.gather(*(s.payment(u,p,100,'XTR','test-charge') for _ in range(20)))
    assert sum(outcomes)==1 and (await s.wallet(u))['available']==10000

@pytest.mark.parametrize('amount,currency',[(99,'XTR'),(100,'USD')])
async def test_A06_payment_mismatch(env,amount,currency):
    s,u=await paid_service(env);p=await s.order(u)
    with pytest.raises(Rejected):await s.payment(u,p,amount,currency,'test-charge')
    assert (await s.wallet(u))['available']==0

async def test_A20_refund(env):
    s,u=await paid_service(env);p=await s.order(u);await s.payment(u,p,100,'XTR','test-charge')
    await s.prepare_refund(p)
    assert (await s.wallet(u))['available']==0
    with pytest.raises(Rejected):await s.prepare_refund(p)
    assert await s.complete_refund(p)
    assert not await s.complete_refund(p)
    assert (await s.wallet(u))['reserved']==0

async def test_A16_budget_race(env):
    pool,cfg,s,u=env
    # demo intentionally has its own fixed limit 1,000,000; prefill to 999,995.
    async with pool.acquire() as c:await c.execute("INSERT INTO budgets VALUES((now() AT TIME ZONE 'UTC')::date,999995)")
    v=await s.identity(202);await s.accept(v)
    a,_=await s.quote(u,'12345','demo');b,_=await s.quote(v,'12345','demo')
    result=await asyncio.gather(s.confirm(u,a),s.confirm(v,b),return_exceptions=True)
    assert sum(isinstance(x,uuid.UUID) for x in result)==1

async def test_DB_constraints(env):
    pool,_,s,u=env
    import asyncpg
    async with pool.acquire() as c:
        with pytest.raises(asyncpg.RaiseError):
            async with c.transaction():await c.execute('UPDATE wallets SET available=available+1 WHERE user_id=$1',u)
        with pytest.raises(asyncpg.RaiseError):await c.execute('DELETE FROM ledger')
    assert await s.reconcile()==0

async def test_A22_demo_isolation(env):
    pool,cfg,s,u=env
    with pytest.raises(Rejected):await s.order(u)
    with pytest.raises(Rejected):await s.payment(u,uuid.uuid4(),100,'XTR','fake')
    q,_=await s.quote(u,'Hello','demo');await s.confirm(u,q)
    async with pool.acquire() as c:
        assert await c.fetchval("SELECT available+reserved FROM wallets WHERE user_id=$1 AND mode='live'",u)==0

async def test_foreign_payload_and_charge_reuse(env):
    s,u=await paid_service(env);v=await s.identity(555);await s.accept(v)
    p=await s.order(u)
    with pytest.raises(Rejected):await s.payment(v,p,100,'XTR','test-charge')
    await s.payment(u,p,100,'XTR','test-charge')
    p2=await s.order(v)
    with pytest.raises(Rejected):await s.payment(v,p2,100,'XTR','test-charge')
    assert (await s.wallet(v))['available']==0

async def test_precheckout_never_credits(env):
    s,u=await paid_service(env);p=await s.order(u)
    assert await s.precheckout(u,p,100,'XTR')
    assert (await s.wallet(u))['available']==0
    # Delayed successful event still applies after sales are disabled.
    from dataclasses import replace
    s.cfg=replace(s.cfg,payments_enabled=False)
    assert await s.payment(u,p,100,'XTR','test-charge')

async def test_transaction_rollback(env):
    pool,cfg,s,u=env
    async with pool.acquire() as c:
        with pytest.raises(RuntimeError):
            async with c.transaction():
                await s.movement(c,u,'demo','rollback-test','demo_grant',7,0)
                raise RuntimeError('injected')
    assert (await s.wallet(u))['available']==10000
    async with pool.acquire() as c:assert not await c.fetchval("SELECT EXISTS(SELECT 1 FROM ledger WHERE event_key='rollback-test')")
