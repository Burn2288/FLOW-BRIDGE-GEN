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
    return {'wallet_mismatches': total, 'limit': limit, 'truncated': total > len(details),
            'details': details, 'funding_mismatches': funding_mismatches,
            'funding_details': funding_details,
            'funding_truncated': funding_mismatches > len(funding_details)}
