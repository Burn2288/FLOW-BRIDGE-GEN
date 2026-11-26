"""Disposable proof of current role lookup across two Mini App instances."""
from dataclasses import replace

from aiohttp.test_utils import TestClient, TestServer

from miniapp.backend.web import create_app
from test_ft022_referrals import signed_start


async def test_http_role_is_not_pilot_admission_and_revocation_is_immediate(env):
    pool, cfg, _, user = env
    cfg = replace(cfg, token='fixture', access_mode='private', admin_ids=(100,))
    path = '/api/v1/admin/capabilities'
    async with TestClient(TestServer(create_app(pool,cfg))) as first, TestClient(TestServer(create_app(pool,cfg))) as second:
        response = await first.post('/api/v1/session', json={'initData': signed_start(cfg.token,100,'')})
        assert response.status == 200
        headers = {'Authorization': 'Bearer ' + (await response.json())['token']}
        assert (await first.get(path, headers=headers)).status == 403
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,'READ_ONLY_ADMIN','synthetic grant')
        """, user)
        for client in (first,second):
            response = await client.get(path+'?role=OWNER_ADMIN', headers=headers)
            assert response.status == 200
            assert await response.json() == {'role':'READ_ONLY_ADMIN','capabilities':['operations.read']}
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,NULL,'synthetic revocation')
        """, user)
        for client in (first,second):
            assert (await client.get(path, headers=headers)).status == 403
