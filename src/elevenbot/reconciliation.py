"""Read-only wallet diagnostics; one row per violated existing check."""

QUERY = '''
WITH wallet_values AS MATERIALIZED (
    SELECT w.user_id,w.mode,w.available,w.reserved,
           coalesce(l.a,0) AS ledger_available,coalesce(l.r,0) AS ledger_reserved,
           coalesce((SELECT sum(j.price) FROM jobs j
                     WHERE j.user_id=w.user_id AND j.mode=w.mode AND j.settlement IS NULL),0) AS jobs_reserved,
           CASE WHEN w.mode='live' THEN coalesce((SELECT sum(p.credits) FROM payments p
                     WHERE p.user_id=w.user_id AND p.status='refunding'),0) ELSE 0 END AS refunds_reserved,
           CASE WHEN w.mode='live' THEN coalesce((SELECT sum(r.dr) FROM ledger r
                     WHERE r.user_id=w.user_id AND r.task_quote_id IS NOT NULL),0) ELSE 0 END AS task_reserved
    FROM wallets w LEFT JOIN
         (SELECT user_id,mode,sum(da) a,sum(dr) r FROM ledger GROUP BY user_id,mode) l USING(user_id,mode)
), violations AS (
    SELECT *, 'wallet_vs_ledger'::text AS check_type FROM wallet_values
    WHERE available<>ledger_available OR reserved<>ledger_reserved
    UNION ALL
    SELECT *, 'reserved_vs_obligations'::text AS check_type FROM wallet_values
    WHERE reserved<>jobs_reserved+refunds_reserved+task_reserved
)
SELECT *,count(*) OVER() AS total FROM violations ORDER BY user_id,mode,check_type LIMIT $1
'''


async def read_report(conn, limit):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('Report limit must be between 1 and 1000')
    rows = await conn.fetch(QUERY, limit)
    total = int(rows[0]['total']) if rows else 0
    details = []
    for row in rows:
        item = {'user_id': str(row['user_id']), 'mode': row['mode'], 'check': row['check_type']}
        if row['check_type'] == 'wallet_vs_ledger':
            item.update(available={'actual': int(row['available']), 'expected': int(row['ledger_available'])},
                        reserved={'actual': int(row['reserved']), 'expected': int(row['ledger_reserved'])})
        else:
            jobs, refunds, tasks = (int(row[k]) for k in ('jobs_reserved','refunds_reserved','task_reserved'))
            item.update(reserved={'actual': int(row['reserved']), 'expected': jobs+refunds+tasks},
                        components={'unsettled_jobs': jobs, 'refunding_payments': refunds, 'task_ledger': tasks})
        details.append(item)
    funding_rows = await conn.fetch("""
        WITH funding AS (
            SELECT user_id,mode,sum(available) AS available
            FROM wallet_funding_lots GROUP BY user_id,mode
        ), violations AS (
            SELECT 'funding_vs_wallet' AS reason,w.user_id,w.mode,
                   NULL::uuid AS ledger_id,w.available AS actual,
                   coalesce(f.available,0) AS expected
            FROM wallets w LEFT JOIN funding f USING(user_id,mode)
            WHERE w.available<>coalesce(f.available,0)
            UNION ALL
            SELECT 'allocation_ownership',d.user_id,d.mode,d.id,NULL,NULL
            FROM wallet_funding_allocations a JOIN ledger d ON d.id=a.debit_ledger_id
            JOIN wallet_funding_lots f ON f.id=a.lot_id
            WHERE (d.user_id,d.mode) IS DISTINCT FROM (f.user_id,f.mode)
            UNION ALL
            SELECT 'payment_provenance',f.user_id,f.mode,f.credit_ledger_id,NULL,NULL
            FROM wallet_funding_lots f
            LEFT JOIN ledger l ON l.id=f.credit_ledger_id
            LEFT JOIN payments p ON p.id=f.payment_id
            WHERE f.origin='PAID' AND (
                (f.user_id,f.mode,f.payment_id) IS DISTINCT FROM (l.user_id,l.mode,l.payment_id)
                OR p.user_id IS DISTINCT FROM f.user_id OR l.kind NOT IN ('payment','topup')
            )
        )
        SELECT *,count(*) OVER() AS total FROM violations
        ORDER BY user_id,mode,reason,ledger_id LIMIT $1
    """, limit)
    funding_mismatches = int(funding_rows[0]['total']) if funding_rows else 0
    funding_details = []
    for row in funding_rows:
        detail = {'status': 'MISMATCH', 'check': row['reason'],
                  'user_id': str(row['user_id']), 'mode': row['mode']}
        if row['ledger_id'] is not None:
            detail['ledger_id'] = str(row['ledger_id'])
        if row['actual'] is not None:
            detail['available'] = {'actual': int(row['actual']), 'expected': int(row['expected'])}
        funding_details.append(detail)
    obligations = await conn.fetch("""
        WITH findings AS (
            SELECT 'reward_ledger_identity' AS reason,r.referrer_id AS user_id,r.capture_id
            FROM referral_rewards r JOIN ledger c ON c.id=r.capture_id
            JOIN referral_policy_snapshots p ON p.reserve_ledger_id=r.reserve_id
            JOIN ledger l ON l.id=r.reward_ledger_id
            LEFT JOIN referral_attributions a ON a.user_id=c.user_id
            WHERE c.kind<>'task_capture' OR c.task_quote_id IS DISTINCT FROM p.quote_id
               OR a.referrer_id IS DISTINCT FROM r.referrer_id OR r.eligible_paid > -c.dr
               OR r.amount<>floor(r.eligible_paid::numeric*p.rate_bps/10000)
               OR l.user_id<>r.referrer_id OR l.kind<>'referral_reward' OR l.da<>r.amount
               OR l.event_key<>'referral-reward:'||c.id
            UNION ALL
            SELECT 'reversal_refund_identity',r.referrer_id,v.capture_id
            FROM referral_reversals v JOIN referral_rewards r USING(capture_id)
            JOIN ledger c ON c.id=v.capture_id JOIN ledger f ON f.id=v.refund_id
            LEFT JOIN ledger l ON l.id=v.ledger_id
            WHERE f.kind<>'task_refund' OR f.task_quote_id IS DISTINCT FROM c.task_quote_id
               OR f.user_id<>c.user_id OR f.da<>-c.dr OR v.amount<>r.amount
               OR (v.debited>0 AND (l.kind IS DISTINCT FROM 'referral_reversal'
                    OR l.user_id IS DISTINCT FROM r.referrer_id OR l.da IS DISTINCT FROM -v.debited))
            UNION ALL
            SELECT 'missing_referral_reversal',r.referrer_id,r.capture_id
            FROM referral_rewards r JOIN ledger c ON c.id=r.capture_id
            JOIN ledger f ON f.task_quote_id=c.task_quote_id AND f.kind='task_refund'
            WHERE NOT EXISTS(SELECT 1 FROM referral_reversals v WHERE v.capture_id=r.capture_id)
            UNION ALL
            SELECT 'negative_referral_debt',user_id,NULL::uuid FROM referral_debt_balances WHERE outstanding<0
        )
        SELECT *,count(*) OVER() AS total FROM findings
        ORDER BY user_id,reason,capture_id LIMIT $1
    """, limit)
    obligation_count = int(obligations[0]['total']) if obligations else 0
    review_rows = await conn.fetch('''SELECT c.payment_id,c.capture_id,c.affected_funding,c.payment_state,c.reason,
        r.eligible_paid,r.amount AS original_reward,coalesce(v.amount,0) AS recorded_reversal,
        count(*) OVER() AS total FROM referral_payment_review_cases c
        JOIN referral_rewards r USING(capture_id)
        LEFT JOIN referral_reversals v USING(capture_id)
        WHERE c.state='required'
        ORDER BY c.payment_id,c.capture_id LIMIT $1''', limit)
    review_count = int(review_rows[0]['total']) if review_rows else 0
    return {'referral_obligation_mismatches': obligation_count,
            'referral_obligations_truncated': obligation_count > len(obligations),
            'referral_obligation_details': [dict(status='MISMATCH', check=row['reason'], user_id=str(row['user_id']),
                capture_id=str(row['capture_id']) if row['capture_id'] else None) for row in obligations],
            'referral_payment_reviews': review_count,
            'referral_payment_reviews_truncated': review_count > len(review_rows),
            'referral_payment_review_details': [dict(payment_id=str(row['payment_id']),
                capture_id=str(row['capture_id']), affected_funding=int(row['affected_funding']),
                payment_state=row['payment_state'], reason=row['reason'], status='RECONCILIATION_REQUIRED',
                affected_funding_basis='POTENTIAL_ALLOCATION', eligible_paid_total=int(row['eligible_paid']),
                original_reward=int(row['original_reward']), recorded_reversal=int(row['recorded_reversal']),
                unresolved_reward_amount_status='NOT_PROVEN')
                for row in review_rows],
            'wallet_mismatches': total, 'limit': limit, 'truncated': total > len(details),
            'details': details, 'funding_mismatches': funding_mismatches,
            'funding_details': funding_details,
            'funding_truncated': funding_mismatches > len(funding_details)}
