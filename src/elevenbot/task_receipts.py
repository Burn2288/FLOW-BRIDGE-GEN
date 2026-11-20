"""Reconcile normalized, authenticated provider billing operations. Server-side only."""
from dataclasses import dataclass
from decimal import Decimal
import re

import httpx

from .core import Rejected


@dataclass(frozen=True)
class FinancialOperation:
    provider: str
    job_id: str
    operation_id: str
    outcome: str
    amount: Decimal
    unit: str


UNKNOWN = 'RECONCILIATION_REQUIRED: возврат агрегатора не подтверждён'


async def _record_review_on(conn, quote_id, remote, finding, *, reopen=False):
    await conn.execute("""
        INSERT INTO task_financial_reconciliation_cases
            (quote_id,provider,provider_job_id,finding)
        SELECT q.id,q.provider,$2,$3
        FROM task_price_quotes q JOIN task_dispatch d ON d.quote_id=q.id
        WHERE q.id=$1
        ON CONFLICT(quote_id) DO UPDATE SET
            provider_job_id=COALESCE(EXCLUDED.provider_job_id,
                task_financial_reconciliation_cases.provider_job_id),
            finding=EXCLUDED.finding,
            attempts=task_financial_reconciliation_cases.attempts+1,
            last_seen_at=now(),
            status='required',resolved_at=NULL,resolution_operation_id=NULL
        WHERE task_financial_reconciliation_cases.status='required' OR $4::boolean
        """, quote_id, remote, finding, reopen)


async def _record_review(pool, quote_id, remote, finding, *, reopen=False):
    async with pool.acquire() as conn, conn.transaction():
        await _record_review_on(conn, quote_id, remote, finding, reopen=reopen)


def _valid_operation(operation, provider, remote):
    return (
        isinstance(operation, FinancialOperation)
        and operation.provider == provider and operation.job_id == remote
        and isinstance(operation.operation_id, str)
        and bool(re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', operation.operation_id))
        and operation.outcome in ('charged','full_refund','partial_refund','rejected_unbilled')
        and isinstance(operation.amount, Decimal) and operation.amount.is_finite()
        and Decimal(0) <= operation.amount <= Decimal('1e12')
        and isinstance(operation.unit, str)
        and bool(re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', operation.unit))
        and ((operation.outcome == 'rejected_unbilled' and operation.amount == 0)
             or (operation.outcome != 'rejected_unbilled' and operation.amount > 0))
    )


async def reconcile_generation(pool, quote_id, sources):
    """A source reads the provider's financial record by remote job ID; never creates work."""
    quote_provider = await pool.fetchval('SELECT provider FROM task_price_quotes WHERE id=$1',quote_id)
    if quote_provider is None:
        return UNKNOWN
    jobs = await pool.fetch("""
        WITH jobs AS (
            SELECT id AS quote_id,provider,provider_id FROM video_jobs
            UNION ALL
            SELECT q.id,q.provider,i.provider_id FROM task_price_quotes q
            JOIN anymodel_image_jobs i ON i.user_id=q.user_id AND i.update_id=q.update_id
            WHERE q.provider='anymodel' AND q.operation='images.generate'
        )
        SELECT j.provider,j.provider_id FROM jobs j WHERE j.quote_id=$1 AND j.provider_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM jobs k WHERE k.provider=j.provider AND k.provider_id=j.provider_id
                          AND k.quote_id<>j.quote_id)
        """,quote_id)
    if len(jobs)!=1:
        await _record_review(pool,quote_id,None,'provider_operation_id_unavailable_or_ambiguous')
        return UNKNOWN
    provider, remote = jobs[0]
    source = sources.get(provider)
    if source is None:
        await _record_review(pool,quote_id,remote,'provider_financial_source_unavailable')
        return UNKNOWN
    # A failed lookup leaves the wallet untouched; the caller may retry this read.
    try:
        operation = await source(remote)
    except (httpx.HTTPError, TimeoutError):
        await _record_review(pool,quote_id,remote,'provider_financial_lookup_failed')
        return UNKNOWN
    if operation is None:
        await _record_review(pool,quote_id,remote,'provider_financial_receipt_unavailable')
        return UNKNOWN
    if not _valid_operation(operation,provider,remote):
        await _record_review(pool,quote_id,remote,'provider_financial_record_invalid')
        raise Rejected('Финансовая запись агрегатора некорректна или относится к другому заданию.')
    async with pool.acquire() as conn, conn.transaction():
        hold = await conn.fetchrow("""SELECT user_id,dr FROM ledger
            WHERE task_quote_id=$1 AND kind='task_reserve' FOR UPDATE""",quote_id)
        if not hold:
            raise Rejected('Резерв задания не найден.')
        values = (remote,quote_id,operation.outcome,operation.amount,operation.unit)
        await conn.execute("""INSERT INTO task_financial_receipts
            (provider,operation_id,provider_job_id,quote_id,outcome,amount,unit)
            VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(provider,operation_id) DO NOTHING""",
            provider,operation.operation_id,*values)
        stored = await conn.fetchrow("""SELECT provider_job_id,quote_id,outcome,amount,unit
            FROM task_financial_receipts WHERE provider=$1 AND operation_id=$2""",provider,operation.operation_id)
        if tuple(stored)!=values:
            await _record_review_on(conn,quote_id,remote,'provider_operation_conflict',reopen=True)
            return 'RECONCILIATION_REQUIRED: конфликт идентификатора операции агрегатора.'
        if operation.outcome=='partial_refund':
            await _record_review_on(conn,quote_id,remote,
                                    'partial_provider_refund_requires_manual_decision',reopen=True)
            return 'RECONCILIATION_REQUIRED: частичный возврат сохранён и ожидает ручного решения.'
        user, tokens = hold
        kind = 'task_capture' if operation.outcome=='charged' else 'task_release'
        await conn.execute("""INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id)
            VALUES(gen_random_uuid(),$1,'live','task-settlement:'||$2::uuid,$3,$4,$5,$2)
            ON CONFLICT(event_key) DO NOTHING""",user,quote_id,kind,0 if kind=='task_capture' else tokens,-tokens)
        if operation.outcome=='full_refund':
            await conn.execute("""INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id)
                SELECT gen_random_uuid(),user_id,'live','task-refund:'||task_quote_id,'task_refund',-dr,0,task_quote_id
                FROM ledger WHERE task_quote_id=$1 AND kind='task_capture'
                ON CONFLICT(event_key) DO NOTHING""",quote_id)
        await conn.execute("""
            UPDATE task_financial_reconciliation_cases SET status='resolved',resolved_at=now(),
                resolution_operation_id=$2,finding=$3,last_seen_at=now()
            WHERE quote_id=$1 AND status='required'
            """,quote_id,operation.operation_id,'provider_outcome_'+operation.outcome)
    return operation.outcome
