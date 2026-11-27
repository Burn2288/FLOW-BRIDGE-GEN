"""RF-01: PostgreSQL attribution through real registration and session paths."""
import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import replace
from unittest.mock import AsyncMock
from urllib.parse import urlencode
from uuid import uuid4

import asyncpg
import pytest
from aiohttp.test_utils import TestClient, TestServer

from elevenbot.core import Rejected, Service
from elevenbot.referrals import start_code
from elevenbot.task_wallet import reserve_task_tokens, settle_task_tokens
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from test_admin_access import event
from test_telegram_consent import DocumentTransport


def signed_start(token, user, payload):
    data = {'auth_date':str(int(time.time())), 'user':json.dumps({'id':user}), 'start_param':payload}
    raw = '\n'.join(f'{key}={value}' for key,value in sorted(data.items()))
    secret = hmac.digest(b'WebAppData', token.encode(), 'sha256')
    return urlencode(data | {'hash':hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()})


async def ready(svc, external):
    user = await svc.identity(external)
    await svc.accept(user)
    return user


async def test_stable_unique_codes_and_collision_without_aborted_transaction(env, monkeypatch):
    pool, cfg, svc, first = env
    await svc.accept(first)
    second = await ready(svc, 101)
    fixed, fresh = 'AAAAAAAAAAAAAAAA', 'BBBBBBBBBBBBBBBB'
    generated = iter([fixed, fixed, fresh])
    monkeypatch.setattr('elevenbot.referrals.secrets.token_urlsafe', lambda _:next(generated))
    assert (await svc.referral_info(first))['code'] == fixed
    assert (await svc.referral_info(first))['code'] == fixed
    assert (await svc.referral_info(second))['code'] == fresh
    assert await pool.fetchval('SELECT count(*) FROM referral_codes') == 2
    # A fresh query in the same issuance path succeeded after the deliberate conflict.
    assert await pool.fetchval('SELECT 1') == 1


async def test_real_start_first_attribution_restart_and_miniapp(env):
    pool, cfg, svc, inviter = env
    cfg = replace(cfg, token='fixture')
    await svc.accept(inviter)
    before = await pool.fetchval('SELECT count(*) FROM ledger')
    code = (await svc.referral_info(inviter))['code']
    assert await pool.fetchval('SELECT count(*) FROM ledger') == before
    bot = DocumentTransport()
    app = TelegramApp(pool, cfg, bot)
    await app.handle(event(1, '/start ref_'+code, chat=201))
    user = await pool.fetchval("SELECT user_id FROM identities WHERE platform='telegram' AND external_id=201")
    assert user and await pool.fetchval('SELECT referrer_id FROM referral_attributions WHERE user_id=$1', user) == inviter
    assert bot.trace[:2] == ['terms.md','privacy.md'] and bot.trace[2].startswith('accept:')
    assert await pool.fetchval('SELECT accepted_at FROM identities WHERE user_id=$1',user) is None
    await app.handle(event(2, callback=bot.trace[2], chat=201))
    other = await ready(svc, 202)
    other_code = (await svc.referral_info(other))['code']
    restarted = TelegramApp(pool, cfg, DocumentTransport())
    await restarted.handle(event(3, '/start ref_'+other_code, chat=201))
    assert await pool.fetchval('SELECT referrer_id FROM referral_attributions WHERE user_id=$1',user) == inviter
    assert await pool.fetchval("SELECT count(*) FROM identities WHERE platform='telegram' AND external_id=201") == 1
    before = await pool.fetchval('SELECT count(*) FROM ledger WHERE user_id=$1',user)
    await restarted.handle(event(4, '/referral', chat=201))
    own = (await restarted.svc.referral_info(user))['code']
    assert own in restarted.bot.sent[-1][0]
    assert await pool.fetchval('SELECT count(*) FROM ledger WHERE user_id=$1',user) == before
    async with TestClient(TestServer(create_app(pool,cfg))) as client:
        response = await client.post('/api/v1/session', json={'initData':signed_start(cfg.token,201,'ref_'+other_code)})
        assert response.status == 200
        headers = {'Authorization':'Bearer '+(await response.json())['token']}
        response = await client.get('/api/v1/referral', headers=headers)
        assert response.status == 200 and await response.json() == {'code':own, 'has_referrer':True}
        assert (await client.get('/api/v1/referral')).status == 401
        assert (await client.get('/api/v1/referral/finances')).status == 401
        data = await client.get('/api/v1/referral/finances?user_id='+str(inviter), headers=headers)
        assert data.status == 200
        finance = await data.json()
        assert finance['code'] == own and finance['invitee_count'] == 0 and finance['history'] == []
        assert 'Приглашено: 0' in restarted.bot.sent[-1][0]
        assert 'Долг: 0' in restarted.bot.sent[-1][0]
        assert (await client.get('/api/v1/referral/finances?page=-1', headers=headers)).status == 400
        data = await client.get('/api/v1/referral/finances?page=1000', headers=headers)
        assert data.status == 200 and (await data.json())['history'] == []
        assert await pool.fetchval('SELECT count(*) FROM ledger WHERE user_id=$1',user) == before
        assert (await client.delete('/api/v1/session', headers=headers)).status in (200, 204)
        assert (await client.get('/api/v1/referral/finances', headers=headers)).status == 401
        response = await client.post('/api/v1/session', json={'initData':signed_start(cfg.token,201,'ref_'+code)})
        headers = {'Authorization':'Bearer '+(await response.json())['token']}
        await pool.execute('UPDATE miniapp_sessions SET expires_at=now() WHERE user_id=$1',user)
        assert (await client.get('/api/v1/referral/finances', headers=headers)).status == 401
    assert await pool.fetchval('SELECT referrer_id FROM referral_attributions WHERE user_id=$1',user) == inviter


async def test_unknown_self_and_no_retroactive_attribution(env):
    pool, cfg, svc, inviter = env
    await svc.accept(inviter)
    code = (await svc.referral_info(inviter))['code']
    app = TelegramApp(pool, cfg, DocumentTransport())
    await app.handle(event(10, '/start ref_UnknownCode00000', chat=210))
    user = await pool.fetchval("SELECT user_id FROM identities WHERE external_id=210 AND platform='telegram'")
    assert user and not await pool.fetchval('SELECT 1 FROM referral_attributions WHERE user_id=$1',user)
    await app.handle(event(11, '/start ref_'+code, chat=210))
    await app.handle(event(12, '/start ref_'+code, chat=100))
    assert not await pool.fetchval('SELECT 1 FROM referral_attributions WHERE user_id=ANY($1::uuid[])',[user,inviter])
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute('INSERT INTO referral_attributions(user_id,referrer_id) VALUES($1,$1)', inviter)
    assert start_code('/start ref_') is None and start_code('/start pay_order') is None


async def test_concurrent_identity_has_one_user_and_one_referrer(env):
    pool, _, svc, first = env
    await svc.accept(first)
    second = await ready(svc,101)
    first_code, second_code = (await svc.referral_info(first))['code'], (await svc.referral_info(second))['code']
    one, two = await asyncio.gather(svc.identity(301,referral_code=first_code),
                                    svc.identity(301,referral_code=second_code))
    assert one == two
    assert await pool.fetchval("SELECT count(*) FROM identities WHERE platform='telegram' AND external_id=301") == 1
    refs = await pool.fetch('SELECT referrer_id FROM referral_attributions WHERE user_id=$1',one)
    assert len(refs) == 1 and refs[0]['referrer_id'] in (first,second)


async def test_pay_start_preserves_existing_route(env):
    pool, cfg, svc, user = env
    await svc.accept(user)
    app = TelegramApp(pool, cfg, DocumentTransport())
    app.topup_ui.callback = AsyncMock()
    await app.handle(event(21, '/start pay_fixture-order', chat=100))
    app.topup_ui.callback.assert_awaited_once_with(user,100,'tucheck','fixture-order')
    assert not await pool.fetchval('SELECT count(*) FROM referral_attributions')


async def test_invitation_requires_consent_and_admission(env):
    pool, cfg, svc, _ = env
    unconsented = await svc.identity(405)
    with pytest.raises(Rejected):
        await svc.referral_info(unconsented)
    private = Service(pool, replace(cfg, access_mode='private', admin_ids=(100,), pilot_user_ids=()))
    with pytest.raises(Rejected):
        await private.identity(406, referral_code='AAAAAAAAAAAAAAAA')
    assert not await pool.fetchval("SELECT 1 FROM identities WHERE platform='telegram' AND external_id=406")


async def test_concurrent_code_issuance_and_database_immutability(env):
    pool, _, svc, user = env
    await svc.accept(user)
    values = await asyncio.gather(*(svc.referral_info(user) for _ in range(5)))
    assert len({v['code'] for v in values}) == 1
    assert await pool.fetchval('SELECT count(*) FROM referral_codes WHERE user_id=$1',user) == 1
    other = await ready(svc, 120)
    code = values[0]['code']
    invited = await svc.identity(121,referral_code=code)
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute('UPDATE referral_attributions SET referrer_id=$2 WHERE user_id=$1', invited, other)
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute('DELETE FROM referral_codes WHERE user_id=$1', user)
    assert await pool.fetchval('SELECT referrer_id FROM referral_attributions WHERE user_id=$1', invited) == user


async def test_configured_invitation_link_in_both_clients(env, monkeypatch):
    from elevenbot.config import Config
    from elevenbot.referrals import referral_link

    pool, cfg, svc, user = env
    await svc.accept(user)
    cfg = replace(cfg, token='fixture', bot_username='Fixture_bot')
    code = (await svc.referral_info(user))['code']
    link = f'https://t.me/Fixture_bot?start=ref_{code}'
    assert referral_link(cfg.bot_username, code) == link
    assert start_code('/start ' + link.split('start=')[1]) == code
    assert referral_link('bad.example/redirect', code) is None
    assert referral_link('Fixture_bot', '../invalid') is None
    monkeypatch.setenv('TELEGRAM_BOT_USERNAME', 'bad.example')
    with pytest.raises(ValueError, match='TELEGRAM_BOT_USERNAME'):
        Config.env()

    bot = DocumentTransport()
    app = TelegramApp(pool, cfg, bot)
    await app.handle(event(601, '/referral', chat=100))
    assert link in bot.sent[-1][0]
    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        login = await client.post('/api/v1/session', json={'initData': signed_start(cfg.token, 100, 'ref_' + code)})
        assert login.status == 200
        headers = {'Authorization': 'Bearer ' + (await login.json())['token']}
        response = await client.get('/api/v1/referral', headers=headers)
        assert (await response.json())['link'] == link


@pytest.mark.parametrize('operation', ['images.generate', 'video', 'audio.speech'])
async def test_paid_durable_task_reward_in_both_clients(env, confirmed_credit, monkeypatch, operation):
    pool, cfg, svc, inviter = env
    cfg = replace(cfg, token='fixture')
    monkeypatch.setenv('RF02_FUNCTIONAL_TEST', 'YES')
    code = (await svc.referral_info(inviter))['code']
    transport = DocumentTransport()
    app = TelegramApp(pool, cfg, transport)
    await app.handle(event(1, '/start ref_' + code, chat=201))
    user = await svc.identity(201)
    await app.handle(event(2, callback=transport.trace[2], chat=201))
    await confirmed_credit(pool, cfg, user, 1000)

    quote = uuid4()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("""
            INSERT INTO task_price_quotes(id,user_id,provider,model_id,operation,request,price,state,update_id)
            VALUES($1,$2,'clodex','fixture-model',$3,'{}','{"total": "1000"}','accepted',100)
            """, quote, user, operation)
        await conn.execute("INSERT INTO task_dispatch(quote_id,state) VALUES($1,'dispatching')", quote)
        await reserve_task_tokens(conn, user, quote, 1000)
    await settle_task_tokens(pool, quote)
    assert await pool.fetchval('SELECT count(*) FROM referral_rewards') == 0

    # Fixture bytes represent the durable result already validated by its adapter.
    async with pool.acquire() as conn, conn.transaction():
        if operation == 'images.generate':
            await conn.execute("""
                INSERT INTO image_works(id,update_id,user_id,model_id,prompt,image,filename)
                VALUES($1,100,$2,'fixture-model','fixture',$3,'test.png')
                """, uuid4(), user, b'image')
        elif operation == 'video':
            await conn.execute("""
                INSERT INTO video_jobs(id,user_id,model_id,prompt,cost_usd,status,video)
                VALUES($1,$2,'fixture-model','fixture',1,'succeeded',$3)
                """, quote, user, b'fixture-video')
        else:
            await conn.execute("""
                INSERT INTO task_speech_works(id,user_id,model_id,title,input,cost_tokens,provider,claimed,audio)
                VALUES($1,$2,'fixture-model','fixture','fixture',1,'clodex',true,$3)
                """, quote, user, b'audio')
        await conn.execute("UPDATE task_dispatch SET state=$2 WHERE quote_id=$1",
                           quote, 'delegated' if operation == 'video' else 'completed')
    await asyncio.gather(settle_task_tokens(pool, quote), settle_task_tokens(pool, quote))
    rewards = await pool.fetch('SELECT eligible_paid,amount FROM referral_rewards')
    assert [tuple(row) for row in rewards] == [(1000, 50)]

    await app.handle(event(3, '/referral', chat=100))
    assert 'Приглашено: 1' in transport.sent[-1][0]
    assert 'Начисление: 50' in transport.sent[-1][0]
    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        for external in (100, 201):
            session = await client.post('/api/v1/session',
                                        json={'initData': signed_start(cfg.token, external, 'ref_' + code)})
            assert session.status == 200
            headers = {'Authorization': 'Bearer ' + (await session.json())['token']}
            response = await client.get('/api/v1/referral/finances', headers=headers)
            assert response.status == 200
            history = (await response.json())['history']
            assert [row['amount'] for row in history] == (['50'] if external == 100 else [])
