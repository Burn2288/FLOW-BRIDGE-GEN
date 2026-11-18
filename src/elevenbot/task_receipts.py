"""Reconcile normalized, authenticated provider billing operations. Server-side only."""
from dataclasses import dataclass
from decimal import Decimal

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


async def reconcile_generation(pool, quote_id, sources):
    """A source reads the provider's financial record by remote job ID; never creates work."""
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
    unknown = 'возврат агрегатора не подтверждён'
    if len(jobs)!=1:
        return unknown
    provider, remote = jobs[0]
    source = sources.get(provider)
    if source is None:
        return unknown
    # A failed lookup leaves the wallet untouched; the caller may retry this read.
    try:
        operation = await source(remote)
    except (httpx.HTTPError, TimeoutError):
        return unknown
    if operation is None:
        return unknown
    if (operation.provider,operation.job_id)!=(provider,remote):
        raise Rejected('Финансовая операция относится к другому заданию.')
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
            raise Rejected('Конфликт финансовой операции агрегатора.')
        if operation.outcome=='partial_refund':
            return 'Частичный возврат сохранён. Пересчёт ожидает решения.'
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
    return operation.outcome
