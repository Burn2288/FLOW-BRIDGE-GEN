"""Disposable PostgreSQL coverage for the shared AD-02 setting."""

import asyncio
from uuid import uuid4

import asyncpg
import pytest
from aiohttp.test_utils import TestClient, TestServer

from elevenbot.aggregate import make_snapshot
from elevenbot.core import Service
from elevenbot.discovery import SnapshotStore
from elevenbot.model_policy import admitted
from elevenbot.model_visibility import VisibilityDenied, confirm
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import account_db, signed


MODEL = ('clodex', 'fixture/image', 'images.generate')
ADMIN_PATH = '/api/v1/admin/model-visibility'


async def test_model_visibility_preview_confirm_rollback_shared_by_both_catalogues(account_db):
    pool, cfg = account_db
    service = Service(pool, cfg)
    actor = await service.identity(100)
    await service.accept(actor)
    snapshot = make_snapshot([
        {'provider': MODEL[0], 'id': MODEL[1], 'title': 'Fixture',
         'availability': 'key_available', 'operations': [MODEL[2]]},
    ], [], [{'provider': 'clodex', 'scope': 'key_available'}])
    SnapshotStore(cfg.catalogue_path).write(snapshot)
    await pool.execute('INSERT INTO approved_models VALUES($1,$2,$3,$4)', *MODEL, 'Fixture')
    telegram = TelegramApp(pool, cfg, None)

    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        login = await client.post('/api/v1/session', json={'initData': signed(cfg.token, 100)})
        assert login.status == 200
        headers = {'Authorization': 'Bearer ' + (await login.json())['token']}

        async def miniapp_visible():
            result = await client.get('/api/v1/catalogue', headers=headers)
            assert result.status == 200
            return MODEL[1] in {row['id'] for row in (await result.json())['models']}

        assert await telegram.store_models(snapshot, 'image', None) == [0]
        assert await miniapp_visible()
        assert (await client.get(ADMIN_PATH, headers=headers)).status == 403
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,'SETTINGS_OPERATOR','synthetic visibility grant')
        """, actor)
        assert (await client.get(ADMIN_PATH, headers=headers)).status == 200
        assert (await client.get('/api/v1/admin/operations', headers=headers)).status == 403
        key = dict(zip(('provider', 'model_id', 'operation'), MODEL))
        hide = {**key, 'visibility': 'HIDDEN'}
        invalid = await client.post(ADMIN_PATH+'/preview', json={**hide, 'visibility': False}, headers=headers)
        assert invalid.status == 400
        response = await client.post(ADMIN_PATH+'/preview', json=hide, headers=headers)
        assert response.status == 200
        previewed = await response.json()
        assert (previewed['visibility'], previewed['desired_visibility'], previewed['version']) == ('VISIBLE', 'HIDDEN', 0)
        assert await miniapp_visible()
        command = {**hide, 'expected_version': previewed['version'], 'request_id': str(uuid4())}
        first, second = await asyncio.gather(*(
            client.post(ADMIN_PATH+'/confirm', json=command, headers=headers) for _ in range(2)
        ))
        assert first.status == second.status == 200
        event = await first.json()
        assert event == await second.json()
        assert await telegram.store_models(snapshot, 'image', None) == []
        assert not await miniapp_visible()
        async with pool.acquire() as conn:
            assert not await admitted(conn, *MODEL)
            assert await admitted(conn, *MODEL, include_hidden=True)
        assert await pool.fetchval('SELECT count(*) FROM model_visibility_events') == 1
        with pytest.raises(asyncpg.RaiseError):
            await pool.execute('UPDATE model_visibility_events SET visibility=previous_visibility')
        stale = await client.post(ADMIN_PATH+'/confirm', json={**command, 'request_id': str(uuid4())}, headers=headers)
        assert stale.status == 409
        rollback = {**key, 'visibility': 'VISIBLE', 'rollback_of': event['version']}
        response = await client.post(ADMIN_PATH+'/preview', json=rollback, headers=headers)
        assert response.status == 200
        restored = await response.json()
        rollback.update(expected_version=restored['version'], request_id=str(uuid4()))
        assert (await client.post(ADMIN_PATH+'/confirm', json=rollback, headers=headers)).status == 200
        assert await telegram.store_models(snapshot, 'image', None) == [0]
        assert await miniapp_visible()
        assert await pool.fetchval('SELECT rollback_of FROM model_visibility_events ORDER BY version DESC LIMIT 1') == event['version']
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,NULL,'synthetic visibility revocation')
        """, actor)
        assert (await client.post(ADMIN_PATH+'/confirm', json=rollback, headers=headers)).status == 403
        assert await miniapp_visible()


async def test_model_visibility_waits_for_role_revocation(env):
    pool, _, service, owner = env
    actor = await service.identity(101)
    await pool.execute("""
        INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
        VALUES($1,$1,'OWNER_ADMIN','synthetic owner')
    """, owner)
    grant = await pool.fetchval("""
        SELECT change_http_admin_role($1,$2,'SETTINGS_OPERATOR',0,$3,'synthetic grant')
    """, actor, owner, uuid4())

    async with pool.acquire() as revoke_conn, pool.acquire() as writer_conn:
        async def publish():
            async with writer_conn.transaction():
                return await confirm(writer_conn, actor, 'clodex', 'flux-schnell', 'images.generate',
                                     'HIDDEN', 0, uuid4())

        async with revoke_conn.transaction():
            await revoke_conn.fetchval("""
                SELECT change_http_admin_role($1,$2,NULL,$3,$4,'synthetic revoke')
            """, actor, owner, grant, uuid4())
            publish_task = asyncio.create_task(publish())
            try:
                async with asyncio.timeout(3):
                    while not await revoke_conn.fetchval(
                        "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=$1",
                        writer_conn.get_server_pid(),
                    ):
                        await asyncio.sleep(0.01)
            except BaseException:
                publish_task.cancel()
                await asyncio.gather(publish_task, return_exceptions=True)
                raise
        with pytest.raises(VisibilityDenied):
            await asyncio.wait_for(publish_task, timeout=3)
    assert not await pool.fetchval('SELECT count(*) FROM model_visibility_events')
