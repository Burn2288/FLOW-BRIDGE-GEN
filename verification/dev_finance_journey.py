"""Drive synthetic Stars, paid generation and referral recovery on the DEV runtime."""
import asyncio
from decimal import Decimal
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode
from uuid import UUID, uuid4

import asyncpg
from aiohttp import ClientSession

from elevenbot.core import Service
from elevenbot.task_receipts import FinancialOperation, reconcile_generation
from elevenbot.referral_rewards import functional_test_database
from scripts.dev_bot import TOKEN, fixture_environment
from scripts.dev_runtime import VIDEO_MODEL, dev_config

FIXTURE_DSN = 'postgresql://postgres:isolated-test-only@127.0.0.1:5432/flowbridge_dev'
ORIGIN = 'http://127.0.0.1:8091'
INVITER = 104
INVITEE = 103
TELEGRAM = 'http://127.0.0.1:8081'

def signed(actor, start=None):
    data = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': actor}), 'query_id': uuid4().hex}
    if start:
        data['start_param'] = start
    message = '\n'.join(f'{key}={value}' for key, value in sorted(data.items()))
    secret = hmac.digest(b'WebAppData', TOKEN.encode(), 'sha256')
    return urlencode(data | {'hash': hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()})

async def request(session, method, path, *, expected=200, origin=ORIGIN, **kwargs):
    async with session.request(method, origin+path, **kwargs) as response:
        assert response.status == expected, (method, path, response.status, await response.text())
        if response.content_type == 'application/json':
            return await response.json()
        return await response.read()

async def login(session, actor, start=None):
    created = await request(session, 'POST', '/api/v1/session', json={'initData': signed(actor, start)})
    return {'Authorization': 'Bearer ' + created['token']}


async def telegram_send(session, actor, payload, matches):
    replies = await request(session, 'GET', '/fixture/replies', origin=TELEGRAM)
    after = max((r['sequence'] for r in replies['replies']), default=0)
    await request(session, 'POST', '/fixture/updates', origin=TELEGRAM, expected=201,
                  json={'chat': actor} | payload)
    for _ in range(120):
        received = (await request(session, 'GET', f'/fixture/replies?after={after}', origin=TELEGRAM))['replies']
        for reply in received:
            if reply['chat'] == actor and (found := matches(reply)):
                return found
        await asyncio.sleep(.25)
    raise AssertionError(f'No matching Telegram reply for {actor}: {payload}')

async def telegram_consent(session, actor, referral=None):
    def accept_button(reply):
        for row in reply['reply_markup'].get('inline_keyboard', ()):
            for button in row:
                if button.get('callback_data', '').startswith('accept:'):
                    return button['callback_data'], reply['message_id']
        return None
    text = '/start ref_'+referral if referral else '/start'
    callback, message = await telegram_send(session, actor, {'text': text}, accept_button)
    await telegram_send(session, actor, {'callback': callback, 'message_id': message},
                        lambda reply: reply['text'])

async def telegram_referral(session, actor):
    return await telegram_send(session, actor, {'text': '/referral'},
                               lambda reply: reply['text'] if 'Ваш код приглашения' in reply['text'] else None)

async def generate(session, headers, model, label):
    quote = await request(session,'POST','/api/v1/quotes',expected=201,headers=headers,
                          json={'model':model,'prompt':'P06 finance '+label})
    job_headers=headers|{'Idempotency-Key':str(uuid4())}
    cmd={'quote_id':quote['quote_id']}
    created = await request(session,'POST','/api/v1/jobs',expected=201,headers=job_headers,json=cmd)
    assert (await request(session,'POST','/api/v1/jobs', headers=job_headers,json=cmd)) == created
    for _ in range(120):
        result=await request(session,'GET','/api/v1/jobs/'+created['id'],headers=headers)
        if result['state']=='completed' and result['result_url']:
            assert await request(session,'GET',result['result_url'],headers=headers)
            return UUID(created['id'])
        assert result['state'] not in {'failed','uncertain','rejected','cancelled'}, result
        await asyncio.sleep(.5)
    raise AssertionError(f'No persisted result for {label}')

async def credit(session, pool, chat, user):
    await request(session, 'POST', '/fixture/stars-payment', origin=TELEGRAM,
                  expected=201, json={'chat': chat})
    replay = await request(session, 'POST', '/fixture/stars-payment', origin=TELEGRAM,
                           expected=201, json={'chat': chat, 'replay': True})
    for _ in range(120):
        order = await pool.fetchrow("""
            SELECT p.id,p.status,count(l.id) AS credits FROM payments p
            LEFT JOIN ledger l ON l.payment_id=p.id AND l.kind='payment'
            WHERE p.user_id=$1 GROUP BY p.id ORDER BY p.created_at DESC LIMIT 1
        """, user)
        if order and order['status']=='succeeded':
            break
        await asyncio.sleep(.25)
    else:
        raise AssertionError('Telegram successful_payment did not confirm order')
    for _ in range(120):
        if await pool.fetchval('SELECT offset_id FROM poll_state WHERE id=1') > replay['update_id']:
            break
        await asyncio.sleep(0.25)
    else:
        raise AssertionError('Telegram gateway did not consume receipt replay')
    assert await pool.fetchval(
        "SELECT count(*) FROM ledger WHERE payment_id=$1 AND kind='payment'", order['id'],
    ) == 1
    return order['id']

async def captured(pool, job):
    for _ in range(120):
        row=await pool.fetchrow("SELECT id,-dr AS amount FROM ledger WHERE task_quote_id=$1 AND kind='task_capture'",job)
        if row:
            return row
        await asyncio.sleep(.5)
    raise AssertionError(f'No capture for {job}')

async def main():
    os.environ.update(fixture_environment())
    assert os.environ.get('DATABASE_URL') == FIXTURE_DSN
    assert functional_test_database() == 'flowbridge_dev'
    cfg=dev_config()
    assert cfg.token == TOKEN and not cfg.payments_enabled
    assert INVITER in cfg.pilot_user_ids and INVITEE in cfg.admin_ids
    async with asyncpg.create_pool(FIXTURE_DSN) as pool, ClientSession() as session:
        assert await pool.fetchval('SELECT current_database()')=='flowbridge_dev'
        async def accepted(external):
            return await pool.fetchval("SELECT accepted_at IS NOT NULL FROM identities WHERE platform='telegram' AND external_id=$1",external)
        if not await accepted(INVITER):
            await telegram_consent(session,INVITER)
        a_headers=await login(session,INVITER)
        invite=await request(session,'GET','/api/v1/referral',headers=a_headers)
        if not await accepted(INVITEE):
            await telegram_consent(session,INVITEE,invite['code'])
        b_headers=await login(session,INVITEE,'ref_'+invite['code'])
        a,b=[await pool.fetchval("SELECT user_id FROM identities WHERE platform='telegram' AND external_id=$1",actor)
             for actor in (INVITER,INVITEE)]
        assert await pool.fetchval('SELECT referrer_id FROM referral_attributions WHERE user_id=$1',b)==a
        prior = await request(session, 'GET', '/api/v1/referral/finances', headers=a_headers)
        assert prior['available'] == prior['debt'] == '0', 'Use untouched fixture actors or a completed prior run.'

        payment_b=await credit(session,pool,INVITEE,b)
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE payment_id=$1 AND kind='payment'", payment_b)==1
        first=await generate(session,b_headers,VIDEO_MODEL,'paid generation')
        capture=await captured(pool,first)
        reward=await pool.fetchrow('SELECT amount,eligible_paid FROM referral_rewards WHERE capture_id=$1',capture['id'])
        assert reward and reward['eligible_paid']==capture['amount'] and reward['amount']==capture['amount']*500//10000
        assert reward['amount']>0
        referral=await request(session,'GET','/api/v1/referral/finances',headers=a_headers)
        assert referral['available']==str(reward['amount']) and referral['debt']=='0'

        await credit(session,pool,INVITER,a)
        assert f"Начисление: {reward['amount']}" in await telegram_referral(session,INVITER)
        for attempt in range(8):
            bonus_spend=await generate(session,a_headers,'flux-schnell',f'spend reward {attempt}')
            await captured(pool,bonus_spend)
            if not await pool.fetchval("SELECT coalesce(sum(available),0) FROM wallet_funding_lots WHERE user_id=$1 AND origin='REFERRAL'",a):
                break
        else:
            raise AssertionError('Referral funding still available after spend attempts')

        remote=await pool.fetchval('SELECT provider_id FROM video_jobs WHERE id=$1',first)
        assert remote.startswith('fixture-')
        async def provider_receipt(job_ref):
            assert job_ref==remote
            return FinancialOperation('clodex', remote, 'p06-refund-'+remote, 'full_refund',
                                      Decimal('0.1'), 'USD', 'p06-charge-'+remote, Decimal('0.1'), 'USD')
        result=await reconcile_generation(pool,first,{'clodex':provider_receipt})
        assert result=='full_refund'
        assert (await reconcile_generation(pool,first,{'clodex':provider_receipt}))=='full_refund'
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_refund'",first)==1
        reversal=await pool.fetchrow('SELECT amount,debited,debt_added FROM referral_reversals WHERE capture_id=$1',capture['id'])
        assert tuple(reversal)==(reward['amount'],0,reward['amount'])
        debt=await request(session,'GET','/api/v1/referral/finances',headers=a_headers)
        assert debt['debt']==str(reward['amount'])
        assert f"Долг: {reward['amount']}" in await telegram_referral(session,INVITER)

        second=await generate(session,b_headers,VIDEO_MODEL,'repay debt')
        next_capture=await captured(pool,second)
        assert await pool.fetchval('SELECT amount FROM referral_debt_repayments WHERE capture_id=$1',next_capture['id'])==reward['amount']
        final=await request(session,'GET','/api/v1/referral/finances',headers=a_headers)
        other=await request(session,'GET','/api/v1/referral/finances',headers=b_headers)
        assert final['debt']=='0' and final['total_rewards']==str(int(prior['total_rewards']) + 2 * reward['amount'])
        assert other['total_rewards']=='0' and not other['history']
        assert 'Долг: 0' in await telegram_referral(session,INVITER)
        assert await Service(pool,cfg).reconcile()==0
        print(json.dumps({'proof':'P06 fixture', 'paid_capture':capture['amount'], 'referral_reward':reward['amount'],
                          'debt_after_confirmed_refund':debt['debt'], 'debt_after_repayment':final['debt'],
                          'transport':'actual Mini App HTTP; synthetic Stars Telegram receipt and normalized provider fixture'},ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
