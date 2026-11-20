"""Reconcile normalized, authenticated provider billing operations. Server-side only."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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
    refunded_operation_id: str | None = None
    original_charge_amount: Decimal | None = None
    original_charge_unit: str | None = None


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
            status='required',resolved_at=NULL,resolution_operation_id=NULL,
            manual_operation_id=NULL,manual_amount=NULL,manual_unit=NULL,
            manual_evidence_ref=NULL,manual_reviewer_external_id=NULL
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
        and ((operation.outcome in ('full_refund','partial_refund')
              and isinstance(operation.refunded_operation_id,str)
              and bool(re.fullmatch(r'[A-Za-z0-9._:-]{1,200}',operation.refunded_operation_id))
              and isinstance(operation.original_charge_amount,Decimal)
              and operation.original_charge_amount.is_finite() and operation.original_charge_amount > 0
              and operation.original_charge_amount <= Decimal('1e12')
              and isinstance(operation.original_charge_unit,str)
              and bool(re.fullmatch(r'[A-Za-z0-9._:-]{1,100}',operation.original_charge_unit)))
             or (operation.outcome not in ('full_refund','partial_refund')
                 and operation.refunded_operation_id is None
                 and operation.original_charge_amount is None
                 and operation.original_charge_unit is None))
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
    except Exception:
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
        if operation.outcome in ('full_refund','partial_refund'):
            charge = await conn.fetchrow("""SELECT provider_job_id,quote_id,amount,unit,outcome
                FROM task_financial_receipts WHERE provider=$1 AND operation_id=$2 AND outcome='charged'
                FOR SHARE""",provider,operation.refunded_operation_id)
            original_amount = charge['amount'] if charge else operation.original_charge_amount
            original_unit = charge['unit'] if charge else operation.original_charge_unit
            invalid_charge = (charge and (charge['outcome'] != 'charged'
                or charge['provider_job_id'] != remote or charge['quote_id'] != quote_id
                or charge['amount'] != operation.original_charge_amount
                or charge['unit'] != operation.original_charge_unit))
            if (invalid_charge or operation.unit != original_unit
                    or operation.amount > original_amount
                    or (operation.outcome == 'full_refund' and operation.amount != original_amount)):
                await _record_review_on(conn,quote_id,remote,'provider_refund_not_bound_to_full_charge',reopen=True)
                return 'RECONCILIATION_REQUIRED: сумма возврата не совпала с подтверждённым списанием.'
            if charge is None:
                prior = await conn.fetchrow("""SELECT quote_id,outcome FROM task_financial_receipts
                    WHERE provider=$1 AND operation_id=$2 FOR SHARE""",provider,operation.refunded_operation_id)
                if prior:
                    await _record_review_on(conn,quote_id,remote,'provider_charge_operation_conflict',reopen=True)
                    return 'RECONCILIATION_REQUIRED: идентификатор списания уже использован.'
                await conn.execute("""INSERT INTO task_financial_receipts
                    (provider,operation_id,provider_job_id,quote_id,outcome,amount,unit)
                    VALUES($1,$2,$3,$4,'charged',$5,$6)""",provider,operation.refunded_operation_id,
                    remote,quote_id,operation.original_charge_amount,operation.original_charge_unit)
        values = (remote,quote_id,operation.outcome,operation.amount,operation.unit,
                  operation.refunded_operation_id)
        await conn.execute("""INSERT INTO task_financial_receipts
            (provider,operation_id,provider_job_id,quote_id,outcome,amount,unit,refunded_operation_id)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT(provider,operation_id) DO NOTHING""",
            provider,operation.operation_id,*values)
        stored = await conn.fetchrow("""SELECT provider_job_id,quote_id,outcome,amount,unit,refunded_operation_id
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
            WHERE quote_id=$1 AND status IN ('required','resolved')
              AND ($4::boolean OR status='required')
            """,quote_id,operation.operation_id,'provider_outcome_'+operation.outcome,
            operation.outcome=='full_refund')
    return operation.outcome


async def manually_review_case(pool, quote_id, *, reviewer_external_id, operation_id, amount, unit, evidence_ref):
    """Record an operator's evidence reference without creating any wallet movement."""
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise Rejected('Некорректная сумма ручной сверки.') from None
    if (not isinstance(reviewer_external_id,int) or reviewer_external_id <= 0
            or not isinstance(operation_id,str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}',operation_id)
            or not amount.is_finite() or amount <= 0 or amount > Decimal('1e12')
            or not isinstance(unit,str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}',unit)
            or not isinstance(evidence_ref,str) or not 8 <= len(evidence_ref) <= 500
            or any(ord(c)<32 for c in evidence_ref)):
        raise Rejected('Для ручной сверки нужны корректные operation ID, сумма, единица и ссылка на доказательство.')
    async with pool.acquire() as conn, conn.transaction():
        case=await conn.fetchrow("""SELECT provider,status,manual_operation_id,manual_amount,manual_unit,
            manual_evidence_ref,manual_reviewer_external_id FROM task_financial_reconciliation_cases
            WHERE quote_id=$1 FOR UPDATE""",quote_id)
        if not case:
            raise Rejected('Кейс ручной сверки не найден.')
        if case['status']=='resolved':
            raise Rejected('Кейс уже закрыт доверенным финансовым событием.')
        if case['status']=='manual_reviewed' and case['manual_operation_id']!=operation_id:
            raise Rejected('Случай уже закрыт другой ручной операцией.')
        values=(case['provider'],operation_id,quote_id,amount,unit,evidence_ref,reviewer_external_id)
        await conn.execute("""INSERT INTO task_financial_reconciliation_manual_audit
            (provider,operation_id,quote_id,amount,unit,evidence_ref,reviewer_external_id)
            VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(provider,operation_id) DO NOTHING""",*values)
        stored=await conn.fetchrow("""SELECT provider,operation_id,quote_id,amount,unit,evidence_ref,reviewer_external_id
            FROM task_financial_reconciliation_manual_audit WHERE provider=$1 AND operation_id=$2""",
            case['provider'],operation_id)
        if tuple(stored)!=values:
            raise Rejected('Идентификатор ручной операции уже использован для другого доказательства или quote.')
        if case['status']=='manual_reviewed':
            return 'manual_reviewed_no_credit'
        await conn.execute("""UPDATE task_financial_reconciliation_cases SET status='manual_reviewed',
            resolved_at=now(),manual_operation_id=$2,manual_amount=$3,manual_unit=$4,
            manual_evidence_ref=$5,manual_reviewer_external_id=$6,
            finding='manual_evidence_recorded_no_wallet_movement',last_seen_at=now()
            WHERE quote_id=$1""",quote_id,operation_id,amount,unit,evidence_ref,reviewer_external_id)
    return 'manual_reviewed_no_credit'
