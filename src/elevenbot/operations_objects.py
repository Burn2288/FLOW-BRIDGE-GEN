"""Bounded object views for the PostgreSQL operations.read capability."""

import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .admin_authority import current_capabilities, has_capability
from .reconciliation import read_report


class OperationsDenied(Exception):
    pass


SECTIONS = {
    'users': 'Пользователи',
    'jobs': 'Задания',
    'queue': 'Очередь',
    'models': 'Модели',
    'providers': 'Провайдеры',
    'payments': 'Платежи',
    'wallets': 'Кошельки',
    'reconciliation': 'Финансовая сверка',
    'incidents': 'Инциденты',
}

JOBS = """
    SELECT 'legacy:' || id AS id, id AS job_id, user_id, model_id,
           'audio.speech' AS operation, NULL::text AS provider, status,
           created_at, completed_at, settlement, lease_until AS next_check,
           (status='queued' AND created_at < now() - interval '15 minutes')
               OR (status='dispatching' AND lease_until < now()) AS overdue
    FROM jobs
    UNION ALL
    SELECT 'task:' || q.id, q.id, q.user_id, q.model_id, q.operation, q.provider,
           coalesce(v.status, i.status, m.status, d.state), coalesce(q.accepted_at,m.created_at),
           NULL, NULL, coalesce(v.next_poll_at,i.next_at,m.next_at),
           (d.state IN ('pending','dispatching') AND q.accepted_at < now() - interval '15 minutes')
              OR (v.status='polling' AND v.next_poll_at < now() - interval '15 minutes')
              OR (i.status='pending' AND i.next_at < now() - interval '15 minutes')
              OR (m.status IN ('queued','polling') AND m.next_at < now() - interval '15 minutes')
    FROM task_price_quotes q
    LEFT JOIN task_dispatch d ON d.quote_id=q.id
    LEFT JOIN video_jobs v ON v.id=q.id AND v.user_id=q.user_id
    LEFT JOIN anymodel_image_jobs i ON q.provider='anymodel' AND q.operation='images.generate'
        AND i.update_id=q.update_id AND i.user_id=q.user_id
    LEFT JOIN clodex_music_jobs m ON m.id=q.id AND m.user_id=q.user_id
    WHERE d.quote_id IS NOT NULL OR m.id IS NOT NULL
"""

ACTIVE_STATES = "'queued','pending','dispatching','submitting','polling','ready','delivering'"

RECORDS = {
    'users': ("""
        SELECT id::text AS id, created_at, blocked FROM users
    """, 'created_at DESC, id'),
    'jobs': (JOBS, 'created_at DESC NULLS LAST, id'),
    'queue': (f"""
        SELECT * FROM ({JOBS}) AS jobs WHERE status IN ({ACTIVE_STATES})
    """, 'overdue DESC NULLS LAST, created_at, id'),
    'models': ("""
        SELECT jsonb_build_array(provider,model_id,operation)::text AS id, provider, model_id, operation,
               title, visibility, visibility_version
        FROM approved_models
    """, 'provider, title, id'),
    'payments': ("""
        SELECT p.id::text AS id, p.user_id, p.provider, p.currency, p.status, p.amount, p.credits, p.created_at,
               t.state AS topup_state, t.returned_minor, t.returned_tokens,
               EXISTS (SELECT 1 FROM referral_payment_review_cases r WHERE r.payment_id=p.id) AS referral_review
        FROM payments p LEFT JOIN topup_orders t ON p.id=t.payment_id
    """, 'created_at DESC, id'),
    'wallets': ("""
        SELECT w.user_id || ':' || w.mode AS id, w.user_id, w.mode, w.available, w.reserved,
               coalesce(d.amount,0) AS payment_debt,
               CASE WHEN w.mode='live' THEN coalesce(r.outstanding,0) ELSE 0 END AS referral_debt
        FROM wallets w LEFT JOIN wallet_debts d USING(user_id,mode)
        LEFT JOIN referral_debt_balances r USING(user_id)
    """, 'id'),
    'incidents': (f"""
        SELECT id, status, created_at,
               CASE WHEN overdue THEN 'overdue_job' ELSE 'job_failure' END AS kind,
               provider, operation
        FROM ({JOBS}) AS jobs
        WHERE overdue OR status IN ('failed','rejected','interrupted','uncertain','unknown','delivery_unknown')
        UNION ALL
        SELECT 'payment:' || p.id, coalesce(t.state,p.status), p.created_at, 'payment_review', p.provider, NULL
        FROM payments p LEFT JOIN topup_orders t ON t.payment_id=p.id
        WHERE p.status='review' OR t.state IN ('unknown','review')
        UNION ALL
        SELECT 'billing:' || q.id, b.finding, q.accepted_at, 'provider_billing_review', q.provider, q.operation
        FROM task_failed_billing_review b JOIN task_price_quotes q ON q.id=b.quote_id
        WHERE b.finding IN ('частичный возврат подтверждён','возврат агрегатора не подтверждён')
        UNION ALL
        SELECT 'referral:' || r.payment_id || ':' || r.capture_id, r.reason, r.created_at,
               'referral_payment_review', p.provider, NULL
        FROM referral_payment_review_cases r JOIN payments p ON p.id=r.payment_id
        WHERE r.state='required'
    """, 'created_at DESC NULLS LAST, id'),
}

DETAIL_TYPES = (
    ('details', 'wallet'),
    ('funding_details', 'funding'),
    ('referral_obligation_details', 'referral_obligation'),
    ('referral_payment_review_details', 'referral_payment'),
)
MAX_RECONCILIATION_ROWS = 100
MAX_OFFSET = 5000


def _display(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (Decimal, int)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict):
        return {key: _display(item) for key, item in value.items()}
    return value


async def _financial_rows(conn):
    # Use the existing diagnostic definitions and cap each category explicitly.
    report = await read_report(conn, MAX_RECONCILIATION_ROWS)
    items = []
    for key, kind in DETAIL_TYPES:
        for row in report[key]:
            identity = [row[field] for field in ('user_id','mode','check','ledger_id','payment_id','capture_id')
                        if field in row]
            items.append(dict(id=json.dumps([kind,*identity], separators=(',',':')), kind=kind, **row))
    truncated = any(report[key] for key in (
        'truncated','funding_truncated','referral_obligations_truncated','referral_payment_reviews_truncated',
    ))
    return items, truncated


def _provider_rows(registry):
    return [
        {
            'id': provider,
            'title': registry.interactive.get(provider, provider),
            'catalogue_adapter': adapter is not None,
            'execution_adapter': provider in registry.launches,
            'manifest_status': registry.manifests.get(provider, {}).get('status'),
            'health': 'NOT_PROVEN',
        }
        for provider, adapter in sorted(registry.adapters.items())
    ]


async def read_objects(conn, actor, registry, section, *, object_id=None, offset=0, limit=20):
    if not has_capability(await current_capabilities(conn, actor), 'operations.read'):
        raise OperationsDenied()
    if section not in SECTIONS:
        raise KeyError(section)
    offset = int(offset) if isinstance(offset, str) else offset
    limit = int(limit) if isinstance(limit, str) else limit
    if (type(offset) is not int or not 0 <= offset <= MAX_OFFSET or type(limit) is not int or not 1 <= limit <= 50
            or object_id is not None and (not isinstance(object_id, str) or not 1 <= len(object_id) <= 1024
                                         or '\0' in object_id or offset)):
        raise ValueError('Invalid operations request')

    truncated = False
    if section in RECORDS:
        statement, order = RECORDS[section]
        rows = await conn.fetch(f"""
            SELECT * FROM ({statement}) AS objects WHERE ($1::text IS NULL OR id=$1)
            ORDER BY {order} LIMIT $2 OFFSET $3
        """, object_id, limit+1, offset)
    else:
        if section == 'providers':
            source = _provider_rows(registry)
        else:
            source, truncated = await _financial_rows(conn)
        rows = [row for row in source if row['id'] == object_id] if object_id is not None else source[offset:offset+limit+1]

    if object_id is not None:
        return _display(dict(rows[0])) if rows else None
    return {'items': [_display(dict(row)) for row in rows[:limit]],
            'has_more': len(rows) > limit and offset+limit <= MAX_OFFSET, 'truncated': truncated}
