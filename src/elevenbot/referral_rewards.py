"""Replayable referral settlement for isolated FUNCTIONAL_TEST runs."""

import os
import uuid

from .referral_reward_policy import CaptureFunding, reward_tokens


def functional_test_enabled():
    return (
        os.environ.get('RF02_FUNCTIONAL_TEST') == 'YES'
        and os.environ.get('DISPOSABLE_POSTGRES_CONFIRM') == 'YES'
    )


async def post_image_rewards(conn, quote_id=None):
    """Post only captured images with an independently persisted result.

    Call inside a transaction. Serialize posts on the immutable capture row
    and the referrer's wallet; the unique reward identity also protects replay.
    """
    rows = await conn.fetch("""
        SELECT c.id,c.user_id,c.task_quote_id,c.dr,p.reserve_ledger_id,p.rate_bps,a.referrer_id
        FROM ledger c JOIN task_price_quotes q ON q.id=c.task_quote_id
        JOIN referral_policy_snapshots p ON p.quote_id=q.id
        JOIN referral_attributions a ON a.user_id=c.user_id
        JOIN anymodel_image_jobs i ON i.update_id=q.update_id AND i.user_id=c.user_id
        JOIN image_works w ON w.update_id=q.update_id AND w.user_id=c.user_id
        WHERE c.kind='task_capture' AND c.mode='live'
          AND q.provider='anymodel' AND q.operation='images.generate'
          AND i.status IN ('ready','delivered')
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
