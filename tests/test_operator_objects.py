"""Operator detail views and support use the same revocable database roles."""

from dataclasses import replace
from uuid import uuid4

from aiohttp.test_utils import TestClient, TestServer

from elevenbot.support_tickets import SupportTickets
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from test_admin_access import event
from test_ft022_referrals import signed_start
from test_ui import Bot


async def _role(pool, actor, role):
    await pool.execute("""
        INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
        VALUES($1,$1,$2,'synthetic operator fixture')
    """, actor, role)


async def test_operator_lists_details_and_financial_findings(env, confirmed_credit):
    pool, cfg, service, actor = env
    cfg = replace(cfg, token='fixture', access_mode='private', admin_ids=(100,), pilot_user_ids=(101,))
    user = await service.identity(101)
    await service.accept(user)
    _, payment = await confirmed_credit(pool,cfg,user,250,'private-fixture-charge')
    quote, _ = await service.quote(user, 'private synthetic prompt', 'demo')
    job = await service.confirm(user,quote)
    await pool.execute("UPDATE jobs SET created_at=now()-interval '20 minutes' WHERE id=$1", job)
    # The diagnostic must distinguish a bad stored total from the append-only ledger.
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute('ALTER TABLE wallets DISABLE TRIGGER wallet_consistent')
        await conn.execute("UPDATE wallets SET available=available+1 WHERE user_id=$1 AND mode='live'", user)
        await conn.execute('ALTER TABLE wallets ENABLE TRIGGER wallet_consistent')
    await _role(pool,actor,'READ_ONLY_ADMIN')

    async with TestClient(TestServer(create_app(pool,cfg))) as client:
        async def login(external):
            response = await client.post('/api/v1/session', json={
                'initData': signed_start(cfg.token,external,'operator-object-fixture')})
            assert response.status == 200
            return {'Authorization':'Bearer '+(await response.json())['token']}

        owner_headers = await login(100)
        outsider_headers = await login(101)
        base = '/api/v1/admin/objects/'
        assert (await client.get(base+'users')).status == 401
        assert (await client.get(base+'users', headers=outsider_headers)).status == 403
        assert (await client.get(base+'users?limit=invalid', headers=outsider_headers)).status == 403
        assert (await client.get(base+'users?limit=5000', headers=owner_headers)).status == 400
        assert (await client.get(base+'unavailable', headers=owner_headers)).status == 404
        assert (await client.get(base+'users?id='+str(uuid4()), headers=owner_headers)).status == 404
        for section in ('users','jobs','queue','models','providers','payments','wallets','reconciliation','incidents'):
            response = await client.get(base+section, headers=owner_headers)
            assert response.status == 200, (section, await response.text())
            listing = await response.json()
            items = listing['items']
            assert items, section
            detail = await client.get(base+section, params={'id':items[0]['id']}, headers=owner_headers)
            assert detail.status == 200, (section, await detail.text())
            assert (await detail.json())['id'] == items[0]['id']
            payload=(await response.text())+(await detail.text())
            for excluded in ('private synthetic prompt','private-fixture-charge','terms_version','merchant_id',
                             'remote_id','credential_ref','external_id','last_error','provider_request_id'):
                assert excluded not in payload, (excluded, section)
        listing = await (await client.get(base+'users?limit=1', headers=owner_headers)).json()
        next_page = await (await client.get(base+'users?limit=1&offset=1', headers=owner_headers)).json()
        assert listing['has_more'] and listing['items'][0]['id'] != next_page['items'][0]['id']
        findings = await (await client.get(base+'reconciliation', headers=owner_headers)).json()
        discrepancy = next(row for row in findings['items'] if row.get('check')=='wallet_vs_ledger')
        assert discrepancy['available'] == {'actual':'251','expected':'250'}
        payment_row = await (await client.get(base+'payments',params={'id':str(payment)},headers=owner_headers)).json()
        assert payment_row['amount']=='100' and payment_row['credits']=='250'
        incident = await (await client.get(base+'incidents',params={'id':'legacy:'+str(job)},headers=owner_headers)).json()
        assert incident['kind']=='overdue_job'
        await _role(pool,actor,None)
        assert (await client.get(base+'users', headers=owner_headers)).status == 403
        assert (await client.get('/api/v1/wallet', headers=owner_headers)).status == 200


async def test_telegram_operator_picks_object_and_replies_using_current_role(env):
    pool, cfg, service, actor = env
    cfg = replace(cfg, access_mode='private', admin_ids=(100,), pilot_user_ids=(101,))
    user = await service.identity(101)
    await service.accept(user)
    support = SupportTickets(pool,cfg)
    ticket = await support.create(101, uuid4(), 'Synthetic owner request')
    bot = Bot()
    app = TelegramApp(pool,cfg,bot)

    async def click(number, callback):
        source = (await app.navigation.read(100)).active_id
        await app.handle(event(number,callback=callback,source_message_id=source))

    await _role(pool,actor,'OWNER_ADMIN')
    await app.handle(event(1010,'/operations'))
    assert 'Обзор операций' in bot.sent[-1][0]
    await click(1011,'opobjects:users:0')
    assert bot.sent[-1][0]=='Пользователи'
    callback=bot.sent[-1][1].inline_keyboard[0][0].callback_data
    await click(1012,callback)
    assert 'Заблокирован: нет' in bot.sent[-1][0]
    await app.handle(event(1013,'/operator_support'))
    callback=bot.sent[-1][1].inline_keyboard[0][0].callback_data
    await click(1014,callback)
    assert 'Synthetic owner request' in bot.sent[-1][0]
    await app.handle(event(1015,'/operator_reply '+str(ticket['id'])+' Synthetic reply'))
    assert 'Synthetic reply' in bot.sent[-1][0]
    assert (await support.read(101,ticket['id']))['status']=='answered'
    await _role(pool,actor,None)
    await app.handle(event(1016,'/operator_reply '+str(ticket['id'])+' Another reply'))
    assert 'Ответ оператора недоступен' in bot.sent[-1][0]
    assert await pool.fetchval('SELECT count(*) FROM support_operator_replies') == 1
