"""OB-02 internal, aggregate-only operational read model (PostgreSQL 16)."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from elevenbot.operations_read_model import read_operations_report


async def _quote(pool, user, provider, model, operation, accepted_at, *, estimate=True):
    quote_id = uuid.uuid4()
    price = {'total': '10', 'provider_amount': '2.5', 'provider_unit': 'USD',
             'estimate': estimate, 'base': '2.5'}
    await pool.execute("""
        INSERT INTO task_price_quotes(id,user_id,provider,model_id,operation,request,price,state,accepted_at)
        VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,'accepted',$8)
        """, quote_id,user,provider,model,operation,
        json.dumps({'prompt':'private fixture prompt'}),json.dumps(price),accepted_at)
    return quote_id


async def _dispatch(pool, user, quote_id, state, at, *, reserve=False, settlement=None):
    await pool.execute('INSERT INTO task_dispatch(quote_id,state) VALUES($1,$2)',quote_id,state)
    if reserve:
        await pool.execute("""
            INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id,created_at)
            VALUES(gen_random_uuid(),$1,'live',$2,'task_reserve',-10,10,$3,$4)
            """,user,f'ob02:reserve:{quote_id}',quote_id,at)
    if settlement == 'capture':
        await pool.execute("""
            INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id,created_at)
            VALUES(gen_random_uuid(),$1,'live',$2,'task_capture',0,-10,$3,$4)
            """,user,f'ob02:capture:{quote_id}',quote_id,at)
    elif settlement == 'release':
        await pool.execute("""
            INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id,created_at)
            VALUES(gen_random_uuid(),$1,'live',$2,'task_release',10,-10,$3,$4)
            """,user,f'ob02:release:{quote_id}',quote_id,at)


async def _receipt(pool, quote_id, provider, outcome, operation_id, amount, at, *,
                  provider_job_id=None, refunded_operation_id=None):
    provider_job_id = provider_job_id or f'job-{operation_id}'
    has_refund_link = await pool.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=current_schema()
              AND table_name='task_financial_receipts'
              AND column_name='refunded_operation_id'
        )
        """)
    if has_refund_link:
        await pool.execute("""
            INSERT INTO task_financial_receipts
                (provider,operation_id,provider_job_id,quote_id,outcome,amount,unit,
                 recorded_at,refunded_operation_id)
            VALUES($1,$2,$3,$4,$5,$6,'USD',$7,$8)
            """,provider,operation_id,provider_job_id,quote_id,outcome,amount,at,
            refunded_operation_id)
    else:
        await pool.execute("""
            INSERT INTO task_financial_receipts
                (provider,operation_id,provider_job_id,quote_id,outcome,amount,unit,recorded_at)
            VALUES($1,$2,$3,$4,$5,$6,'USD',$7)
            """,provider,operation_id,provider_job_id,quote_id,outcome,amount,at)


async def test_aggregate_report_separates_operations_cost_evidence_and_timezone(env,confirmed_credit):
    pool,cfg,service,owner=env
    second=await service.identity(101)
    await service.accept(second)
    for user,ext in ((owner,100),(second,101)):
        async with pool.acquire() as conn,conn.transaction():
            await service.movement(conn,user,'live',f'ob02-credit-{ext}','pilot_grant',500,0)

    timezone_name='Asia/Tokyo'
    local_start=datetime.now(ZoneInfo(timezone_name)).replace(hour=0,minute=0,second=0,microsecond=0)
    start=local_start.astimezone(timezone.utc)
    end=start+timedelta(days=2)
    legacy_at=start+timedelta(hours=5)
    legacy_quote,legacy_job=uuid.uuid4(),uuid.uuid4()
    budget_day=legacy_at.date()
    await pool.execute('INSERT INTO budgets(day,used) VALUES($1,0) ON CONFLICT(day) DO NOTHING',budget_day)
    await pool.execute("""
        INSERT INTO quotes(id,user_id,mode,text_content,voice,speed,price,cost_bound,tariff,created_at)
        VALUES($1,$2,'demo','private legacy prompt','legacy-fixture-model',1,10,10,'fixture',$3)
        """,legacy_quote,owner,legacy_at)
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("""
            INSERT INTO jobs(id,user_id,quote_id,mode,price,cost_bound,budget_day,status,model_id,created_at)
            VALUES($1,$2,$3,'demo',10,10,$4,'queued','legacy-fixture-model',$5)
            """,legacy_job,owner,legacy_quote,budget_day,legacy_at)
        await service.movement(conn,owner,'demo',f'ob02:legacy-reserve:{legacy_job}','reserve',-10,10,legacy_job)
        await service.movement(conn,owner,'demo',f'ob02:legacy-capture:{legacy_job}','capture',0,-10,legacy_job)
        await conn.execute("""
            UPDATE jobs SET status='succeeded',settlement='capture',completed_at=$2 WHERE id=$1
            """,legacy_job,legacy_at)
    q_success=await _quote(pool,owner,'clodex','video-a','video.generate',start,estimate=False)
    q_failed=await _quote(pool,second,'clodex','video-b','video.generate',start+timedelta(hours=25))
    q_uncertain=await _quote(pool,owner,'anymodel','image-a','images.generate',start+timedelta(hours=1))
    q_refunded=await _quote(pool,second,'anymodel','image-b','images.generate',end-timedelta(microseconds=1))
    q_at_end=await _quote(pool,owner,'excluded-provider','excluded-model','images.generate',end)

    await _dispatch(pool,owner,q_success,'completed',start,reserve=True,settlement='capture')
    await _dispatch(pool,second,q_failed,'rejected',start+timedelta(hours=25),reserve=True,settlement='release')
    await _dispatch(pool,owner,q_uncertain,'uncertain',start+timedelta(hours=1),reserve=True)
    await _dispatch(pool,second,q_refunded,'completed',end-timedelta(microseconds=1),reserve=True,settlement='capture')
    await _dispatch(pool,owner,q_at_end,'pending',end,reserve=True)

    await _receipt(pool,q_success,'clodex','charged','success-charge','2.5',start)
    await _receipt(pool,q_uncertain,'anymodel','charged','uncertain-charge','2.5',
                   start+timedelta(hours=1),provider_job_id='job-uncertain')
    await _receipt(pool,q_uncertain,'anymodel','partial_refund','uncertain-partial','0.5',
                   start+timedelta(hours=1),provider_job_id='job-uncertain',
                   refunded_operation_id='uncertain-charge')
    await _receipt(pool,q_refunded,'anymodel','charged','refund-charge','3.0',
                   end-timedelta(microseconds=1),provider_job_id='job-refunded')
    await _receipt(pool,q_refunded,'anymodel','full_refund','refund-full','3.0',
                   end-timedelta(microseconds=1),provider_job_id='job-refunded',
                   refunded_operation_id='refund-charge')
    await pool.execute("""
        INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id)
        SELECT gen_random_uuid(),user_id,'live','ob02:task-refund:'||task_quote_id,
               'task_refund',-dr,0,task_quote_id
        FROM ledger WHERE task_quote_id=$1 AND kind='task_capture'
        ON CONFLICT(event_key) DO NOTHING
        """,q_refunded)
    await pool.execute("""
        INSERT INTO task_price_accounting(quote_id,user_debit,user_refund,provider_cost,reference)
        VALUES($1,10,0,1.25,'fixture-private-accounting-reference')
        """,q_success)
    await pool.execute("""
        INSERT INTO video_jobs(id,user_id,model_id,prompt,cost_usd,provider,status,created_at)
        VALUES($1,$2,'video-a','private prompt',0.75,'clodex','succeeded',$3),
              ($4,$5,'video-b','private prompt',NULL,'clodex','failed',$6),
              ($7,$2,'image-a','private prompt',1.25,'anymodel','failed',$8),
              ($9,$5,'image-b','private prompt',NULL,'anymodel','failed',$10)
        """,q_success,owner,start,q_failed,second,start+timedelta(hours=25),
        q_uncertain,start+timedelta(hours=1),q_refunded,end-timedelta(microseconds=1))

    # Synthetic payment receipt and its refund lifecycle; this does not call a payment provider.
    payment_service,payment_id=await confirmed_credit(pool,cfg,second,50,'ob02-fixture-charge')
    await payment_service.prepare_refund(payment_id)
    assert await payment_service.complete_refund(payment_id)

    before_wallets=[tuple(r) for r in await pool.fetch('SELECT user_id,mode,available,reserved FROM wallets ORDER BY user_id,mode')]
    before_ledger=[tuple(r) for r in await pool.fetch('SELECT id,event_key,kind,da,dr,task_quote_id,payment_id FROM ledger ORDER BY id')]

    report=await read_operations_report(pool,start,end,timezone_name=timezone_name,limit=100)
    repeated=await read_operations_report(pool,start,end,timezone_name=timezone_name,limit=100)
    assert report==repeated
    assert report['window']=={'start':start.isoformat(),'end_exclusive':end.isoformat(),'timezone':timezone_name}

    daily=report['tasks_by_period_and_status']['groups']
    assert report['tasks_by_period_and_status']['group_count']==5
    assert {(r['local_day'].isoformat() if hasattr(r['local_day'],'isoformat') else r['local_day'],r['source'],r['status']) for r in daily}=={
        (local_start.date().isoformat(),'legacy_job','succeeded'),
        (local_start.date().isoformat(),'quoted_task','completed'),
        (local_start.date().isoformat(),'quoted_task','uncertain'),
        ((local_start.date()+timedelta(days=1)).isoformat(),'quoted_task','completed'),
        ((local_start.date()+timedelta(days=1)).isoformat(),'quoted_task','rejected')}
    assert all('excluded-provider' not in json.dumps(r) for r in report.values())
    assert {r['provider'] for r in report['tasks_by_provider_and_model']['groups']}=={'anymodel','clodex','unknown'}
    assert {r['status'] for r in report['provider_job_statuses']['groups']}=={'failed','succeeded'}

    movements=report['wallet_movements']['groups']
    kinds={r['kind'] for r in movements}
    assert {'task_reserve','task_capture','task_release','task_refund','payment','refund_hold','refund'} <= kinds
    assert all(r['unit']=='internal_wallet_unit' for r in movements)
    assert {r['currency'] for r in report['payments']['groups']}=={'XTR'}
    assert {r['outcome'] for r in report['provider_receipts']['groups']}=={
        'charged','full_refund','partial_refund'}

    accounted=report['provider_cost_evidence']['groups']
    success_cost=next(r for r in accounted if r['provider']=='clodex')
    assert success_cost['known_count']==1 and success_cost['unknown_count']==1
    assert success_cost['confirmed_unbilled_count']==0
    assert success_cost['amount']=='1.25'
    image_cost=next(r for r in accounted if r['provider']=='anymodel')
    assert image_cost['known_count']==0 and image_cost['unknown_count']==2 and image_cost['amount'] is None
    assert report['provider_cost_coverage']=={
        'without_operator_cost':3,'without_cost_or_bill_evidence':1,'accepted_task_count':4}
    quoted=next(r for r in report['provider_quote_costs']['groups'] if r['provider']=='clodex')
    assert quoted['non_estimated_quote_count']==1 and quoted['estimated_quote_count']==1
    assert Decimal(quoted['quoted_amount'])==Decimal('5.0')
    video=report['video_quote_estimates']['groups']
    video_unknown=next(r for r in video if r['model_id']=='video-b')
    assert video_unknown['provider']=='clodex' and video_unknown['unknown_count']==1
    image_unknown=next(r for r in video if r['model_id']=='image-b')
    assert image_unknown['unknown_count']==1 and image_unknown['quoted_amount'] is None
    queue=report['reconciliation_queue']['groups']
    assert any(r['source']=='task_dispatch' and r['status']=='uncertain' for r in queue)
    assert any(r['source']=='billing_review' and r['status']=='partial_refund_review' for r in queue)

    serialized=json.dumps(report,ensure_ascii=False,default=str)
    assert 'margin' not in serialized.lower()
    for forbidden in (str(owner),str(second),'private fixture prompt','fixture-private-accounting-reference',
                      'job-success-charge','private prompt'):
        assert forbidden not in serialized
    assert [tuple(r) for r in await pool.fetch('SELECT user_id,mode,available,reserved FROM wallets ORDER BY user_id,mode')]==before_wallets
    assert [tuple(r) for r in await pool.fetch('SELECT id,event_key,kind,da,dr,task_quote_id,payment_id FROM ledger ORDER BY id')]==before_ledger

    limited=await read_operations_report(pool,start,end,timezone_name=timezone_name,limit=1)
    assert limited['tasks_by_period_and_status']['truncated']
    assert len(limited['tasks_by_period_and_status']['groups'])==1
    assert [tuple(r) for r in await pool.fetch('SELECT id,event_key,kind,da,dr,task_quote_id,payment_id FROM ledger ORDER BY id')]==before_ledger


async def test_empty_period_returns_empty_groups_without_invented_costs(env):
    pool,_,_,_=env
    start=datetime(2100,1,1,tzinfo=timezone.utc)
    report=await read_operations_report(pool,start,start+timedelta(days=1),timezone_name='UTC')
    for section in ('tasks_by_period_and_status','tasks_by_provider_and_model','provider_job_statuses',
                    'wallet_movements','payments','reconciliation_queue','provider_cost_evidence',
                    'provider_quote_costs','provider_receipts','video_quote_estimates'):
        assert report[section]['groups']==[]
        assert report[section]['group_count']==0
    assert report['provider_cost_coverage']=={
        'without_operator_cost':0,'without_cost_or_bill_evidence':0,'accepted_task_count':0}


@pytest.mark.parametrize('start,end,timezone_name,limit',[
    (datetime(2026,1,1),datetime(2026,1,2,tzinfo=timezone.utc),'UTC',10),
    (datetime(2026,1,2,tzinfo=timezone.utc),datetime(2026,1,1,tzinfo=timezone.utc),'UTC',10),
    (datetime(2025,1,1,tzinfo=timezone.utc),datetime(2026,2,2,tzinfo=timezone.utc),'UTC',10),
    (datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,1,2,tzinfo=timezone.utc),'Not/AZone',10),
    (datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,1,2,tzinfo=timezone.utc),'UTC',201),
    (datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,1,2,tzinfo=timezone.utc),'UTC',True),
])
async def test_window_validation_fails_before_database_access(start,end,timezone_name,limit):
    class NoDatabase:
        def acquire(self):
            raise AssertionError('invalid windows must be rejected before DB access')
    with pytest.raises(ValueError):
        await read_operations_report(NoDatabase(),start,end,timezone_name=timezone_name,limit=limit)

async def test_operational_snapshot_keeps_financial_liabilities_separate(env):
    pool, cfg, service, user = env
    quote, _ = await service.quote(user, 'fixture-only text', 'demo')
    await service.confirm(user, quote)
    now = datetime.now(timezone.utc)
    report = await read_operations_report(pool, now-timedelta(days=1), now+timedelta(days=1))
    snapshot = report['current_state']
    assert snapshot['evidence'] == 'DATABASE_SNAPSHOT'
    assert snapshot['registered_users'] == snapshot['legacy_queued_jobs'] == snapshot['wallets_with_holds'] == 1
    assert snapshot['live_reserved_tokens'] == snapshot['live_payment_debt_tokens'] == snapshot['referral_debt_tokens'] == '0'
    assert snapshot['users_with_payment_debt'] == snapshot['users_with_referral_debt'] == 0
    assert snapshot['provider_health'] == 'NOT_PROVEN'
    assert str(user) not in json.dumps(snapshot) and 'fixture-only text' not in json.dumps(snapshot)
