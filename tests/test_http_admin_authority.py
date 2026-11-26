"""Disposable proof of current role lookup across two Mini App instances."""
from dataclasses import replace

from aiohttp.test_utils import TestClient, TestServer

from miniapp.backend.web import create_app
from test_ft022_referrals import signed_start


async def test_http_role_is_not_pilot_admission_and_revocation_is_immediate(env):
    pool, cfg, _, user = env
    cfg = replace(cfg, token='fixture', access_mode='private', admin_ids=(100,))
    path = '/api/v1/admin/capabilities'
    report_path = '/api/v1/admin/operations?start=2026-01-01T00:00:00Z&end=2026-01-02T00:00:00Z'
    async with TestClient(TestServer(create_app(pool,cfg))) as first, TestClient(TestServer(create_app(pool,cfg))) as second:
        response = await first.post('/api/v1/session', json={'initData': signed_start(cfg.token,100,'fixture-admin-launch')})
        assert response.status == 200
        headers = {'Authorization': 'Bearer ' + (await response.json())['token']}
        assert (await first.get(path, headers=headers)).status == 403
        assert (await first.get(report_path, headers=headers)).status == 403
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,'READ_ONLY_ADMIN','synthetic grant')
        """, user)
        for client in (first,second):
            response = await client.get(path+'?role=OWNER_ADMIN', headers=headers)
            assert response.status == 200
            assert await response.json() == {'role':'READ_ONLY_ADMIN','capabilities':['operations.read']}
        report = await second.get(report_path, headers=headers)
        assert report.status == 200 and (await report.json())['current_state']['registered_users'] == 1
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,NULL,'synthetic revocation')
        """, user)
        for client in (first,second):
            assert (await client.get(path, headers=headers)).status == 403
            assert (await client.get(report_path, headers=headers)).status == 403


async def test_trusted_role_event_is_serialized_and_replay_safe(env):
    import asyncio
    from uuid import uuid4
    import asyncpg
    import pytest

    pool, _, service, owner = env
    target = await service.identity(101)
    await pool.execute("""INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
        VALUES($1,$1,'OWNER_ADMIN','synthetic bootstrap')""", owner)
    event = uuid4()
    sql = 'SELECT change_http_admin_role($1,$2,$3,$4,$5,$6)'
    async def grant():
        return await pool.fetchval(sql,target,owner,'READ_ONLY_ADMIN',0,event,'synthetic grant')
    first, second = await asyncio.gather(grant(),grant())
    assert first == second
    with pytest.raises(asyncpg.RaiseError, match='stale'):
        await pool.fetchval(sql,target,owner,None,0,uuid4(),'stale revoke')
    async with pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        await conn.fetchval(sql,target,owner,None,first,uuid4(),'rolled back revoke')
        await tx.rollback()
    last = await pool.fetchval(sql,target,owner,None,first,uuid4(),'synthetic revoke')
    assert last > first
    assert await pool.fetchval('SELECT count(*) FROM http_admin_role_events WHERE subject_id=$1',target) == 2
