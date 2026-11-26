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


async def test_support_reply_is_owned_and_revocable(env):
    from uuid import uuid4

    pool, cfg, service, operator = env
    owner = await service.identity(101)
    stranger = await service.identity(102)
    await service.accept(owner)
    await service.accept(stranger)
    cfg = replace(cfg, token='fixture', access_mode='private', admin_ids=(100,), pilot_user_ids=(101,102))
    async with TestClient(TestServer(create_app(pool,cfg))) as app:
        response = await app.post('/api/v1/session',json={'initData':signed_start(cfg.token,100,'support-fixture')})
        headers={'Authorization':'Bearer '+(await response.json())['token']}
        async def owner_session(subject):
            response = await app.post('/api/v1/session', json={
                'initData': signed_start(cfg.token, subject, 'support-owner-fixture')})
            assert response.status == 200
            return {'Authorization': 'Bearer ' + (await response.json())['token']}

        own_headers = await owner_session(101)
        other_headers = await owner_session(102)
        owner_path = '/api/v1/support'
        payload = {'request_id': str(uuid4()), 'text': 'Synthetic request'}
        assert (await app.post(owner_path, json={**payload, 'attachment':'fixture'},
                               headers=own_headers)).status == 400
        created = await app.post(owner_path, json=payload, headers=own_headers)
        assert created.status == 200
        ticket = await created.json()
        repeat = await app.post(owner_path, json=payload, headers=own_headers)
        assert repeat.status == 200 and (await repeat.json())['id'] == ticket['id']
        owner_detail = owner_path + '?ticket_id=' + ticket['id']
        assert (await app.get(owner_detail, headers=other_headers)).status == 404
        path='/api/v1/admin/support/reply'
        body={'ticket_id':str(ticket['id']),'request_id':str(uuid4()),'text':'Synthetic reply'}
        assert (await app.post(path,json=body,headers=headers)).status==403
        assert (await app.get('/api/v1/admin/support',headers=headers)).status==403
        await pool.execute("""INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,'SUPPORT_OPERATOR','synthetic grant')""",operator)
        inbox=await app.get('/api/v1/admin/support',headers=headers)
        assert inbox.status==200 and (await inbox.json())['tickets'][0]['id']==str(ticket['id'])
        detail=await app.get('/api/v1/admin/support?ticket_id='+str(ticket['id']),headers=headers)
        assert detail.status==200 and (await detail.json())['messages'][0]['body']=='Synthetic request'
        saved=await app.post(path,json=body,headers=headers)
        replay=await app.post(path,json=body,headers=headers)
        assert saved.status==replay.status==200 and await saved.json()==await replay.json()
        await pool.execute("""INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,NULL,'synthetic revoke')""",operator)
        assert (await app.post(path,json=body,headers=headers)).status==403
        detail = await app.get(owner_detail, headers=own_headers)
        assert detail.status == 200
        history = await detail.json()
    assert history['status']=='answered'
    assert {item['body'] for item in history['messages']}=={'Synthetic request','Synthetic reply'}
    assert await pool.fetchval('SELECT count(*) FROM support_operator_replies')==1


async def test_telegram_operations_report_uses_current_database_role(env):
    from elevenbot.telegram import TelegramApp
    from test_admin_access import event
    from test_ui import Bot

    pool, cfg, _, actor = env
    first = TelegramApp(pool, cfg, Bot())
    second = TelegramApp(pool, cfg, Bot())
    await first.handle(event(600, '/operations'))
    assert first.bot.sent[-1][0] == 'Обзор операций недоступен.'
    await pool.execute("""
        INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
        VALUES($1,$1,'READ_ONLY_ADMIN','synthetic grant')
    """, actor)
    await first.handle(event(601, '/operations'))
    text = first.bot.sent[-1][0]
    assert 'Пользователи сейчас: 1' in text and 'В очереди сейчас: 0' in text
    assert 'Модели:' in text and 'Платежи:' in text
    await second.handle(event(602, '/operations'))
    assert second.bot.sent[-1][0] == text
    await pool.execute("""
        INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
        VALUES($1,$1,NULL,'synthetic revoke')
    """, actor)
    for index, app in enumerate((first, second), start=603):
        await app.handle(event(index, '/operations'))
        assert app.bot.sent[-1][0] == 'Обзор операций недоступен.'
