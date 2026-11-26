"""Replayable referral settlement for isolated FUNCTIONAL_TEST runs."""

import os
import uuid

from .referral_reward_policy import CaptureFunding, reward_tokens


_DEV_DATABASE_URL = 'postgresql://postgres:isolated-test-only@127.0.0.1:5432/flowbridge_dev'


def functional_test_database():
    if os.environ.get('RF02_FUNCTIONAL_TEST') != 'YES':
        return None
    # The isolated launcher sets this only after validating the dedicated fixed DSN.
    if (os.environ.get('FLOWBRIDGE_DEV_FIXTURE') == 'YES'
            and os.environ.get('DATABASE_URL') == _DEV_DATABASE_URL
            and not os.environ.get('TEST_DATABASE_URL')
            and not os.environ.get('DATABASE_MIGRATION_URL')):
        return 'flowbridge_dev'
    from scripts.disposable_test_db import require_disposable_dsn
    try:
        require_disposable_dsn(os.environ)
    except ValueError:
        return None
    return 'elevenbot_test'


def functional_test_enabled():
    return functional_test_database() is not None


async def lock_referral_settlement(conn):
    await conn.execute('SELECT pg_advisory_xact_lock(921181, 52)')


async def _lock_wallet(conn, user):
    await conn.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live' FOR UPDATE", user)


async def _debit(conn, ledger_id, user, kind, key, amount):
    await conn.execute("""
        INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr)
        VALUES($1,$2,'live',$3,$4,-$5::bigint,0)
    """, ledger_id, user, key, kind, amount)


async def reverse_confirmed_refund(conn, quote_id):
    """Compensate only an existing guarded task_refund, even after deactivation."""
    if not conn.is_in_transaction():
        raise RuntimeError('referral reversal requires a transaction')
    await lock_referral_settlement(conn)
    row = await conn.fetchrow("""
        SELECT r.capture_id,r.referrer_id,r.amount,f.id AS refund_id
        FROM referral_rewards r JOIN ledger c ON c.id=r.capture_id
        JOIN ledger f ON f.task_quote_id=c.task_quote_id AND f.kind='task_refund'
        WHERE c.task_quote_id=$1 AND c.kind='task_capture'
          AND f.user_id=c.user_id AND f.da=-c.dr
          AND NOT EXISTS (SELECT 1 FROM referral_reversals v WHERE v.capture_id=r.capture_id)
    """, quote_id)
    if not row:
        return
    await _lock_wallet(conn, row['referrer_id'])
    available = await conn.fetchval("""
        SELECT coalesce(sum(available),0)::bigint FROM wallet_funding_lots
        WHERE user_id=$1 AND mode='live' AND origin='REFERRAL'
    """, row['referrer_id'])
    debited = min(available, row['amount'])
    ledger_id = uuid.uuid4() if debited else None
    await conn.execute("""
        INSERT INTO referral_reversals(capture_id,refund_id,amount,debited,debt_added,ledger_id)
        VALUES($1,$2,$3,$4,$5,$6)
    """, row['capture_id'], row['refund_id'], row['amount'], debited, row['amount']-debited, ledger_id)
    if debited:
        await _debit(conn, ledger_id, row['referrer_id'], 'referral_reversal',
                     f"referral-reversal:{row['capture_id']}", debited)


async def _repay_debt(conn, user, capture_id, reward):
    debt = await conn.fetchval('SELECT coalesce((SELECT outstanding FROM referral_debt_balances WHERE user_id=$1),0)', user)
    amount = min(debt, reward)
    if amount<=0:
        return
    ledger_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO referral_debt_repayments(capture_id,amount,ledger_id) VALUES($1,$2,$3)
    """, capture_id, amount, ledger_id)
    await _debit(conn, ledger_id, user, 'referral_debt_repay', f'referral-debt-repay:{capture_id}', amount)


async def post_task_rewards(conn, quote_id=None):
    """Post only captures backed by an independently persisted result.

    Call inside a transaction. Serialize posts on the immutable capture row
    and the referrer's wallet; the unique reward identity also protects replay.
    """
    database = functional_test_database()
    if database is None:
        return
    if not conn.is_in_transaction():
        raise RuntimeError('referral reward requires a transaction')
    if not await conn.fetchval("""
        SELECT current_database()=$1::text AND (
            $1<>'flowbridge_dev' OR
            (session_user='postgres' AND inet_server_addr()='127.0.0.1'::inet AND inet_server_port()=5432)
        )
    """, database):
        return
    await lock_referral_settlement(conn)
    rows = await conn.fetch("""
        SELECT c.id,c.user_id,c.task_quote_id,c.dr,p.reserve_ledger_id,p.rate_bps,a.referrer_id
        FROM ledger c JOIN task_price_quotes q ON q.id=c.task_quote_id
        JOIN referral_policy_snapshots p ON p.quote_id=q.id
        JOIN referral_attributions a ON a.user_id=c.user_id
        WHERE c.kind='task_capture' AND c.mode='live'
          AND (
              (q.operation='images.generate' AND EXISTS (
                  SELECT 1 FROM image_works w
                  WHERE w.update_id=q.update_id AND w.user_id=c.user_id AND w.model_id=q.model_id
              ) AND (q.provider='clodex' OR (q.provider='anymodel' AND EXISTS (
                  SELECT 1 FROM anymodel_image_jobs i
                  WHERE i.update_id=q.update_id AND i.user_id=c.user_id AND i.status IN ('ready','delivered')
              ))))
              OR (q.operation='video' AND EXISTS (
                  SELECT 1 FROM video_jobs v WHERE v.id=q.id AND v.user_id=c.user_id
                    AND v.provider=q.provider AND v.model_id=q.model_id
                    AND v.status='succeeded' AND v.video IS NOT NULL
              ))
              OR (q.operation='audio.speech' AND EXISTS (
                  SELECT 1 FROM task_speech_works s WHERE s.id=q.id AND s.user_id=c.user_id
                    AND s.provider=q.provider AND s.model_id=q.model_id AND s.audio IS NOT NULL
              ))
          )
          AND ($1::uuid IS NULL OR q.id=$1)
          AND NOT EXISTS (SELECT 1 FROM referral_rewards r WHERE r.capture_id=c.id)
          AND NOT EXISTS (SELECT 1 FROM ledger f WHERE f.task_quote_id=q.id AND f.kind='task_refund')
        ORDER BY a.referrer_id,c.id
        FOR UPDATE OF c SKIP LOCKED
    """, quote_id)
    for row in rows:
        sources = await conn.fetch("""
            SELECT a.amount,f.origin,f.user_id,f.mode,l.kind,l.user_id AS credit_user,
                   l.mode AS credit_mode,l.payment_id AS credit_payment,p.id AS payment_id,
                   p.user_id AS payer,p.status,t.state,t.returned_minor
            FROM wallet_funding_allocations a JOIN wallet_funding_lots f ON f.id=a.lot_id
            LEFT JOIN ledger l ON l.id=f.credit_ledger_id
            LEFT JOIN payments p ON p.id=f.payment_id
            LEFT JOIN topup_orders t ON t.payment_id=p.id
            WHERE a.debit_ledger_id=$1
        """, row['reserve_ledger_id'])
        if sum(s['amount'] for s in sources) != -row['dr']:
            continue
        paid = sum(s['amount'] for s in sources if (
            s['origin'] == 'PAID' and s['mode'] == s['credit_mode'] == 'live'
            and s['user_id'] == s['credit_user'] == s['payer'] == row['user_id']
            and s['payment_id'] == s['credit_payment'] and s['kind'] in ('payment', 'topup')
            and s['status'] == 'succeeded'
            and (s['kind'] == 'payment' or (s['state'] == 'paid' and s['returned_minor'] == 0))
        ))
        amount = reward_tokens(CaptureFunding(0, 0, paid, 0), 0, row['rate_bps'])
        if not amount:
            continue
        await _lock_wallet(conn, row['referrer_id'])
        reward_id = uuid.uuid4()
        inserted = await conn.fetchval("""
            INSERT INTO referral_rewards(capture_id,reserve_id,referrer_id,eligible_paid,amount,reward_ledger_id)
            VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(capture_id) DO NOTHING RETURNING capture_id
        """, row['id'], row['reserve_ledger_id'], row['referrer_id'], paid, amount, reward_id)
        if not inserted:
            continue
        await conn.execute("""
            INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr)
            VALUES($1,$2,'live',$3,'referral_reward',$4,0)
        """, reward_id, row['referrer_id'], f"referral-reward:{row['id']}", amount)
        await _repay_debt(conn, row['referrer_id'], row['id'], amount)

async def record_payment_reviews(conn):
    """Bounded, replay-safe scan of persisted payment states; posts no movements."""
    await conn.execute("""
        INSERT INTO referral_payment_review_cases
            (payment_id,capture_id,reward_ledger_id,affected_funding,payment_state,reason)
        SELECT p.id,r.capture_id,r.reward_ledger_id,sum(a.amount),p.status,
               CASE WHEN p.status='refunded' OR t.state='refunded' THEN 'payment_refunded'
                    WHEN coalesce(t.returned_minor,0)>0 THEN 'partial_payment_return'
                    ELSE 'payment_review' END
        FROM referral_rewards r
        JOIN wallet_funding_allocations a ON a.debit_ledger_id=r.reserve_id
        JOIN wallet_funding_lots f ON f.id=a.lot_id AND f.origin='PAID'
        JOIN payments p ON p.id=f.payment_id AND p.user_id=f.user_id
        LEFT JOIN topup_orders t ON t.payment_id=p.id
        WHERE (p.status IN ('review','refunded') OR t.state IN ('review','refunded') OR t.returned_minor>0)
          AND NOT EXISTS (SELECT 1 FROM referral_payment_review_cases c
                          WHERE c.payment_id=p.id AND c.capture_id=r.capture_id)
        GROUP BY p.id,r.capture_id,r.reward_ledger_id,p.status,t.state,t.returned_minor
        ORDER BY p.id,r.capture_id LIMIT 100
        ON CONFLICT(payment_id,capture_id) DO NOTHING
    """)
