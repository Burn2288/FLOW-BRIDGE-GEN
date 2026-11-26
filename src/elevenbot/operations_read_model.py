"""Bounded, aggregate-only internal operational and financial read models.

This module is intentionally not mounted as an HTTP endpoint. It exposes no
account identifiers, prompts, provider operation identifiers, secrets, or
free-text reconciliation evidence.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_WINDOW = timedelta(days=366)
MAX_GROUPS = 200


def _validate_window(start, end, timezone_name, limit):
    if (not isinstance(start, datetime) or not isinstance(end, datetime)
            or start.tzinfo is None or end.tzinfo is None
            or start.utcoffset() is None or end.utcoffset() is None):
        raise ValueError('Start and end must be timezone-aware datetimes')
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if end <= start or end - start > MAX_WINDOW:
        raise ValueError('Report window must be positive and at most 366 days')
    if type(limit) is not int or not 1 <= limit <= MAX_GROUPS:
        raise ValueError(f'Group limit must be between 1 and {MAX_GROUPS}')
    if not isinstance(timezone_name, str) or len(timezone_name) > 64:
        raise ValueError('Invalid timezone')
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Invalid timezone') from None
    return start, end


async def _groups(conn, sql, start, end, timezone_name, limit):
    # Some grouped queries do not need the timezone, but share the same bound
    # parameter shape. Keep PostgreSQL's parameter typing explicit in all cases.
    bound_sql = f"SELECT * FROM ({sql}) AS report WHERE $3::text IS NOT NULL"
    rows = await conn.fetch(bound_sql, start, end, timezone_name, limit)
    total = int(rows[0]['total_groups']) if rows else 0
    groups = []
    for row in rows:
        item = {}
        for key, value in row.items():
            if key == 'total_groups':
                continue
            if isinstance(value, Decimal):
                value = str(value)
            elif isinstance(value, (date, datetime)):
                value = value.isoformat()
            item[key] = value
        groups.append(item)
    return {'groups': groups, 'group_count': total, 'truncated': total > len(groups)}


TASK_DAILY = '''
WITH task_events AS (
    SELECT q.accepted_at AS happened_at, 'quoted_task'::text AS source,
           d.state AS status
    FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id
    WHERE q.state='accepted' AND q.accepted_at >= $1 AND q.accepted_at < $2
    UNION ALL
    SELECT j.created_at, 'legacy_job', j.status
    FROM jobs j WHERE j.created_at >= $1 AND j.created_at < $2
)
SELECT date_trunc('day', happened_at AT TIME ZONE $3)::date AS local_day,
       source,status,count(*)::bigint AS task_count,count(*) OVER()::bigint AS total_groups
FROM task_events
GROUP BY local_day,source,status
ORDER BY local_day,source,status LIMIT $4
'''

MODEL_PROVIDER = '''
WITH task_models AS (
    SELECT q.provider,q.model_id,'quoted_task'::text AS source
    FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id
    WHERE q.state='accepted' AND q.accepted_at >= $1 AND q.accepted_at < $2
    UNION ALL
    SELECT 'unknown'::text,coalesce(j.model_id,'unknown'),'legacy_job'
    FROM jobs j WHERE j.created_at >= $1 AND j.created_at < $2
)
SELECT source,provider,model_id,count(*)::bigint AS task_count,
       count(*) OVER()::bigint AS total_groups
FROM task_models GROUP BY source,provider,model_id
ORDER BY source,provider,model_id LIMIT $4
'''

PROVIDER_STATES = '''
WITH states AS (
    SELECT v.created_at AS happened_at,v.provider,v.model_id,v.status,'video'::text AS kind
    FROM video_jobs v JOIN task_dispatch d ON d.quote_id=v.id
    WHERE v.created_at >= $1 AND v.created_at < $2
    UNION ALL
    SELECT q.accepted_at,'anymodel',i.model_id,i.status,'image'
    FROM anymodel_image_jobs i JOIN task_price_quotes q
      ON q.user_id=i.user_id AND q.update_id=i.update_id AND q.provider='anymodel'
       AND q.operation='images.generate'
    WHERE q.accepted_at >= $1 AND q.accepted_at < $2
    UNION ALL
    SELECT m.created_at,m.provider,q.model_id,m.status,'music'
    FROM clodex_music_jobs m JOIN task_price_quotes q ON q.id=m.id
    WHERE m.created_at >= $1 AND m.created_at < $2
)
SELECT kind,provider,model_id,status,count(*)::bigint AS task_count,
       count(*) OVER()::bigint AS total_groups
FROM states GROUP BY kind,provider,model_id,status
ORDER BY kind,provider,model_id,status LIMIT $4
'''

LEDGER_MOVEMENTS = '''
SELECT date_trunc('day',created_at AT TIME ZONE $3)::date AS local_day,
       mode,kind,'internal_wallet_unit'::text AS unit,count(*)::bigint AS operation_count,
       coalesce(sum(da),0)::numeric AS available_delta,
       coalesce(sum(dr),0)::numeric AS reserved_delta,
       count(*) OVER()::bigint AS total_groups
FROM ledger WHERE created_at >= $1 AND created_at < $2
GROUP BY local_day,mode,kind ORDER BY local_day,mode,kind LIMIT $4
'''

PAYMENT_RECORDS = '''
SELECT date_trunc('day',p.created_at AT TIME ZONE $3)::date AS local_day,
       p.provider,p.currency,p.status,count(*)::bigint AS payment_count,
       coalesce(sum(p.amount),0)::numeric AS order_amount,
       count(*) OVER()::bigint AS total_groups
FROM payments p WHERE p.created_at >= $1 AND p.created_at < $2
GROUP BY local_day,p.provider,p.currency,p.status
ORDER BY local_day,p.provider,p.currency,p.status LIMIT $4
'''

RECONCILIATION_QUEUE = '''
WITH cases AS (
    SELECT 'task_dispatch'::text AS source,d.state AS status,q.provider,q.operation
    FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id
    WHERE q.accepted_at >= $1 AND q.accepted_at < $2 AND d.state='uncertain'
    UNION ALL
    SELECT 'legacy_job','uncertain','unknown','unknown'
    FROM jobs j WHERE j.created_at >= $1 AND j.created_at < $2 AND j.status='uncertain'
    UNION ALL
    SELECT 'billing_review',CASE
             WHEN v.finding='частичный возврат подтверждён' THEN 'partial_refund_review'
             ELSE 'provider_refund_unknown' END,q.provider,q.operation
    FROM task_failed_billing_review v JOIN task_price_quotes q ON q.id=v.quote_id
    WHERE q.accepted_at >= $1 AND q.accepted_at < $2
      AND v.finding IN ('частичный возврат подтверждён','возврат агрегатора не подтверждён')
    UNION ALL
    SELECT 'topup_order',t.state,p.provider,'payment'
    FROM topup_orders t JOIN payments p ON p.id=t.payment_id
    WHERE t.created_at >= $1 AND t.created_at < $2 AND t.state IN ('unknown','review')
)
SELECT source,status,provider,operation,count(*)::bigint AS case_count,
       count(*) OVER()::bigint AS total_groups
FROM cases GROUP BY source,status,provider,operation
ORDER BY source,status,provider,operation LIMIT $4
'''

PROVIDER_COST_EVIDENCE = '''
WITH receipt_flags AS (
    SELECT quote_id,
           bool_or(outcome='rejected_unbilled')
             AND NOT bool_or(outcome IN ('charged','full_refund','partial_refund')) AS confirmed_unbilled
    FROM task_financial_receipts GROUP BY quote_id
)
SELECT q.provider,q.price->>'provider_unit' AS unit,
       'operator_reconciled'::text AS evidence,
       count(*) FILTER (WHERE a.provider_cost IS NOT NULL)::bigint AS known_count,
       count(*) FILTER (WHERE a.provider_cost IS NULL AND NOT coalesce(r.confirmed_unbilled,false))::bigint AS unknown_count,
       count(*) FILTER (WHERE a.provider_cost IS NULL AND coalesce(r.confirmed_unbilled,false))::bigint AS confirmed_unbilled_count,
       sum(a.provider_cost)::numeric AS amount,
       count(*) OVER()::bigint AS total_groups
FROM task_price_quotes q LEFT JOIN task_price_accounting a ON a.quote_id=q.id
LEFT JOIN receipt_flags r ON r.quote_id=q.id
WHERE q.state='accepted' AND q.accepted_at >= $1 AND q.accepted_at < $2
GROUP BY q.provider,q.price->>'provider_unit'
ORDER BY provider,unit LIMIT $4
'''

QUOTE_COST_ESTIMATES = '''
SELECT q.provider,q.price->>'provider_unit' AS unit,'quote_cost'::text AS evidence,
       count(*) FILTER (WHERE q.price->>'estimate'='false')::bigint AS non_estimated_quote_count,
       count(*) FILTER (WHERE q.price->>'estimate'='true')::bigint AS estimated_quote_count,
       coalesce(sum((q.price->>'provider_amount')::numeric),0)::numeric AS quoted_amount,
       count(*) OVER()::bigint AS total_groups
FROM task_price_quotes q
WHERE q.state='accepted' AND q.accepted_at >= $1 AND q.accepted_at < $2
  AND q.price ? 'provider_amount'
GROUP BY q.provider,q.price->>'provider_unit'
ORDER BY provider,unit LIMIT $4
'''

PROVIDER_RECEIPTS = '''
SELECT provider,outcome,unit,count(*)::bigint AS receipt_count,
       coalesce(sum(amount),0)::numeric AS provider_reported_amount,
       count(*) OVER()::bigint AS total_groups
FROM task_financial_receipts
WHERE recorded_at >= $1 AND recorded_at < $2
GROUP BY provider,outcome,unit ORDER BY provider,outcome,unit LIMIT $4
'''

VIDEO_ESTIMATES = '''
SELECT provider,model_id,'USD'::text AS unit,count(*)::bigint AS quote_count,
       count(*) FILTER (WHERE cost_usd IS NULL)::bigint AS unknown_count,
       sum(cost_usd)::numeric AS quoted_amount,
       count(*) OVER()::bigint AS total_groups
FROM video_jobs WHERE created_at >= $1 AND created_at < $2
GROUP BY provider,model_id ORDER BY provider,model_id LIMIT $4
'''

UNKNOWN_COST = '''
WITH receipt_flags AS (
    SELECT quote_id,bool_or(outcome IN ('charged','full_refund','rejected_unbilled')) AS has_cost_or_bill_evidence
    FROM task_financial_receipts GROUP BY quote_id
)
SELECT count(*) FILTER (WHERE a.provider_cost IS NULL)::bigint AS without_operator_cost,
       count(*) FILTER (WHERE a.provider_cost IS NULL AND NOT coalesce(r.has_cost_or_bill_evidence,false))::bigint AS without_cost_or_bill_evidence,
       count(*)::bigint AS accepted_task_count
FROM task_price_quotes q LEFT JOIN task_price_accounting a ON a.quote_id=q.id
LEFT JOIN receipt_flags r ON r.quote_id=q.id
WHERE q.state='accepted' AND q.accepted_at >= $1 AND q.accepted_at < $2
'''


CURRENT_OPERATIONS = '''
SELECT
    (SELECT count(*) FROM users)::bigint AS registered_users,
    (SELECT count(*) FROM jobs WHERE status='queued')::bigint AS legacy_queued_jobs,
    (SELECT count(*) FROM jobs WHERE status IN ('dispatching','uncertain'))::bigint AS legacy_running_or_uncertain,
    (SELECT count(*) FROM task_dispatch WHERE state='pending')::bigint AS quoted_pending_tasks,
    (SELECT count(*) FROM task_dispatch WHERE state IN ('dispatching','uncertain'))::bigint AS quoted_running_or_uncertain,
    (SELECT count(*) FROM wallets WHERE reserved>0)::bigint AS wallets_with_holds,
    (SELECT coalesce(sum(reserved),0) FROM wallets WHERE mode='live') AS live_reserved_tokens,
    (SELECT count(DISTINCT user_id) FROM wallet_debts WHERE amount>0)::bigint AS users_with_payment_debt,
    (SELECT coalesce(sum(amount),0) FROM wallet_debts WHERE mode='live') AS live_payment_debt_tokens,
    (SELECT count(*) FROM referral_debt_balances WHERE outstanding>0)::bigint AS users_with_referral_debt,
    (SELECT coalesce(sum(outstanding),0) FROM referral_debt_balances WHERE outstanding>0) AS referral_debt_tokens,
    (SELECT count(*) FROM referral_payment_review_cases WHERE state='required')::bigint AS referral_payment_review_cases
'''


async def read_operations_report(pool, start, end, *, timezone_name='UTC', limit=100):
    """Return bounded aggregate facts without writing or identifying users.

    Time windows are half-open in absolute time; only grouping uses the selected
    IANA timezone. This API is internal and deliberately has no HTTP route.
    """
    start, end = _validate_window(start, end, timezone_name, limit)
    async with pool.acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
        result = {
            'window': {'start': start.isoformat(), 'end_exclusive': end.isoformat(),
                       'timezone': timezone_name},
            'limits': {'max_days': 366, 'max_groups_per_section': MAX_GROUPS,
                       'group_limit': limit},
            'tasks_by_period_and_status': await _groups(conn,TASK_DAILY,start,end,timezone_name,limit),
            'tasks_by_provider_and_model': await _groups(conn,MODEL_PROVIDER,start,end,timezone_name,limit),
            'provider_job_statuses': await _groups(conn,PROVIDER_STATES,start,end,timezone_name,limit),
            'wallet_movements': await _groups(conn,LEDGER_MOVEMENTS,start,end,timezone_name,limit),
            'payments': await _groups(conn,PAYMENT_RECORDS,start,end,timezone_name,limit),
            'reconciliation_queue': await _groups(conn,RECONCILIATION_QUEUE,start,end,timezone_name,limit),
            'provider_cost_evidence': await _groups(conn,PROVIDER_COST_EVIDENCE,start,end,timezone_name,limit),
            'provider_quote_costs': await _groups(conn,QUOTE_COST_ESTIMATES,start,end,timezone_name,limit),
            'provider_receipts': await _groups(conn,PROVIDER_RECEIPTS,start,end,timezone_name,limit),
            'video_quote_estimates': await _groups(conn,VIDEO_ESTIMATES,start,end,timezone_name,limit),
        }
        snapshot = await conn.fetchrow(CURRENT_OPERATIONS)
        result['current_state'] = {'evidence': 'DATABASE_SNAPSHOT',
                                   'provider_health': 'NOT_PROVEN',
                                   **{key: str(value) if key.endswith('_tokens') else int(value)
                                      for key,value in snapshot.items()}}
        unknown = await conn.fetchrow(UNKNOWN_COST,start,end)
        result['provider_cost_coverage'] = {key: int(value) for key,value in unknown.items()}
    return result
