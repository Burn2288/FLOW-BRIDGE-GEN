"""Disposable PostgreSQL read-only report and legacy halt semantics."""
import json
import sys

import pytest
from elevenbot.core import Service
from miniapp.tests.test_miniapp import account_db
from test_ft020_http_image import image_api, quote, create


async def test_report_has_both_checks_and_does_not_mutate(env, monkeypatch, capsys):
    pool, cfg, svc, user = env
    q, _ = await svc.quote(user, 'hello', 'demo')
    await svc.confirm(user, q)
    assert (await svc.reconciliation_report())['wallet_mismatches'] == 0
    # Only the isolated fixture schema is altered; restore its trigger immediately.
    async with pool.acquire() as conn:
        await conn.execute('ALTER TABLE wallets DISABLE TRIGGER wallet_consistent')
        try:
            await conn.execute("UPDATE wallets SET available=available+1,reserved=reserved+2 WHERE user_id=$1 AND mode='demo'",user)
        finally:
            await conn.execute('ALTER TABLE wallets ENABLE TRIGGER wallet_consistent')

    async def snapshot():
        return (await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode'),
                await pool.fetch('SELECT * FROM ledger ORDER BY id'),
                await pool.fetch('SELECT * FROM jobs ORDER BY id'),
                await pool.fetch('SELECT * FROM payments ORDER BY id'),
                await pool.fetch('SELECT * FROM settings ORDER BY id'))
    before = await snapshot()
    report = await svc.reconciliation_report()
    assert report['funding_mismatches'] == 1
    assert report['wallet_mismatches'] == 2 and not report['truncated']
    assert {r['check'] for r in report['details']} == {'wallet_vs_ledger','reserved_vs_obligations'}
    assert all(r['user_id']==str(user) and r['mode']=='demo' for r in report['details'])
    first = next(r for r in report['details'] if r['check']=='wallet_vs_ledger')
    assert first['available']['actual'] == first['available']['expected']+1
    assert first['reserved'] == {'actual':7,'expected':5}
    second = next(r for r in report['details'] if r['check']=='reserved_vs_obligations')
    assert second['reserved']=={'actual':7,'expected':5}
    assert second['components']=={'unsettled_jobs':5,'refunding_payments':0,'task_ledger':0}
    limited = await svc.reconciliation_report(1)
    assert limited['wallet_mismatches']==2 and limited['truncated'] and len(limited['details'])==1
    for invalid in (0, 1001, True):
        with pytest.raises(ValueError):await svc.reconciliation_report(invalid)
    assert await snapshot()==before

    # Exercise real CLI dispatch without closing the shared test fixture pool.
    import elevenbot.__main__ as cli
    class PoolView:
        def acquire(self):return pool.acquire()
        async def close(self):pass
    async def connect(_dsn):return PoolView()
    monkeypatch.setattr(cli,'connect',connect)
    monkeypatch.setattr(cli.Config,'env',lambda *_:cfg)
    monkeypatch.setattr(sys,'argv',['elevenbot','reconcile-report','--limit','1'])
    await cli.main()
    result=json.loads(capsys.readouterr().out)
    assert result['wallet_mismatches']==2 and result['truncated']
    assert await snapshot()==before
    monkeypatch.setattr(sys,'argv',['elevenbot','reconcile'])
    await cli.main()
    assert json.loads(capsys.readouterr().out)=={'wallet_mismatches':2}
    assert await pool.fetchval('SELECT halted FROM settings WHERE id=1') is True


async def test_live_refund_obligation_component(env, confirmed_credit):
    pool, cfg, _, user = env
    service, order = await confirmed_credit(pool,cfg,user,100)
    await service.prepare_refund(order)
    assert (await service.reconciliation_report())['wallet_mismatches']==0
    async with pool.acquire() as conn:
        await conn.execute('ALTER TABLE wallets DISABLE TRIGGER wallet_consistent')
        try:
            await conn.execute("UPDATE wallets SET reserved=reserved+1 WHERE user_id=$1 AND mode='live'",user)
        finally:
            await conn.execute('ALTER TABLE wallets ENABLE TRIGGER wallet_consistent')
    report=await service.reconciliation_report()
    item=next(r for r in report['details'] if r['check']=='reserved_vs_obligations' and r['mode']=='live')
    assert item['reserved']=={'actual':101,'expected':100}
    assert item['components']=={'unsettled_jobs':0,'refunding_payments':100,'task_ledger':0}
    assert await pool.fetchval('SELECT halted FROM settings WHERE id=1') is False


async def test_live_task_ledger_obligation_component(image_api, account_db):
    pool, users, client, headers, _, deferred, _, _ = image_api
    _, cfg = account_db
    q=await quote(client,headers[0])
    assert (await create(client,headers[0],q)).status==201 and len(deferred)==1
    service=Service(pool,cfg)
    assert (await service.reconciliation_report())['wallet_mismatches']==0
    async with pool.acquire() as conn:
        await conn.execute('ALTER TABLE wallets DISABLE TRIGGER wallet_consistent')
        try:
            await conn.execute("UPDATE wallets SET reserved=reserved+1 WHERE user_id=$1 AND mode='live'",users[0])
        finally:
            await conn.execute('ALTER TABLE wallets ENABLE TRIGGER wallet_consistent')
    report=await service.reconciliation_report()
    item=next(r for r in report['details'] if r['check']=='reserved_vs_obligations' and r['user_id']==str(users[0]))
    assert item['reserved']=={'actual':11,'expected':10}
    assert item['components']=={'unsettled_jobs':0,'refunding_payments':0,'task_ledger':10}
    assert await pool.fetchval('SELECT halted FROM settings WHERE id=1') is False
