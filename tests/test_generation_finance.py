import asyncio
from dataclasses import replace
from decimal import Decimal
import os
from pathlib import Path
import sys

import httpx
import pytest

from elevenbot.anymodel_video import AnyModelVideoPilot, AnyModelVideoProvider, MODEL
from elevenbot.core import Rejected
from elevenbot.pricing import Request
from elevenbot.tariff_admin import default_params
from elevenbot.task_receipts import FinancialOperation, reconcile_generation, manually_resolve_no_refund_case
from elevenbot.task_wallet import settle_task_tokens
from elevenbot.telegram import TelegramApp
from test_admin_access import event
from test_task_refusal import Price, Transport


@pytest.mark.parametrize('refund_while_held',[False,True])
async def test_provider_finance(env,confirmed_credit,refund_while_held):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                anymodel_key='fixture',anymodel_video_live=True,interaction_limit=10)
    await confirmed_credit(pool,cfg,user,100)
    calls=[]
    stages=iter(['processing','failed'])
    def respond(req):
        calls.append((req.method,req.url.path))
        if req.method=='POST':
            return httpx.Response(202,json={'request_id':'job-1'},headers={'x-9router-connection-id':'fixture'})
        assert req.url.path=='/v1/videos/job-1'
        return httpx.Response(200,json={'status':next(stages)})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        bot=Transport(False)
        app=TelegramApp(pool,cfg,bot)
        app.anymodel_video=AnyModelVideoPilot(pool,cfg,api=AnyModelVideoProvider(cfg.anymodel_key,client=http))
        app.pricing.adapters['anymodel']=Price()
        quote=await app.pricing.quote(user,Request('anymodel',MODEL,'video','Fixture','Video',default_params('anymodel','video')))
        await app.handle(event(1,callback=f'amconfirm:{quote.id}'))
        async def balance():
            return tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE mode='live' AND user_id=$1",user))

        operation=None
        async def financial_lookup(remote):
            assert remote=='job-1'
            if isinstance(operation,Exception):
                raise operation
            return operation
        assert app.providers.financial_sources == {}
        missing_source=await reconcile_generation(pool,quote.id,{})
        assert missing_source.startswith('RECONCILIATION_REQUIRED:')
        case=await pool.fetchrow('SELECT provider,provider_job_id,status,finding,attempts FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)
        assert tuple(case)==('anymodel','job-1','required','provider_financial_source_unavailable',1)
        app.providers.financial_sources['anymodel']=financial_lookup
        async def reconcile():
            return await reconcile_generation(pool,quote.id,{'anymodel':financial_lookup})
        def receipt(key,outcome,amount,remote='job-1'):
            return FinancialOperation(
                'anymodel',remote,key,outcome,Decimal(amount),'USD',
                'charge' if outcome in ('full_refund','partial_refund') else None,
                Decimal('2') if outcome in ('full_refund','partial_refund') else None,
                'USD' if outcome in ('full_refund','partial_refund') else None,
            )

        assert await app.anymodel_video.poll_one(bot)
        assert (await reconcile()).startswith('RECONCILIATION_REQUIRED:')
        case=await pool.fetchrow('SELECT provider,provider_job_id,status,finding,attempts FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)
        assert tuple(case)==('anymodel','job-1','required','provider_financial_receipt_unavailable',2)
        operation=TimeoutError()
        await app.handle(event(8,text=f'/price_account {quote.id}'))
        assert await balance()==(40,60)
        assert await pool.fetchval('SELECT attempts FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)==3
        operation=None
        if not refund_while_held:
            operation=receipt('charge','charged','2')
            await app.handle(event(9,text=f'/price_account {quote.id}'))
            assert await balance()==(40,0)
            assert await pool.fetchval('SELECT status FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)=='resolved'
        await pool.execute('UPDATE video_jobs SET next_poll_at=now()')
        assert await app.anymodel_video.poll_one(bot)
        await settle_task_tokens(pool)
        assert await pool.fetchval('SELECT finding FROM task_failed_billing_review WHERE quote_id=$1',quote.id)=='возврат агрегатора не подтверждён'
        assert await balance()==((40,60) if refund_while_held else (40,0))
        operation=receipt('wrong','full_refund','2','other-job')
        with pytest.raises(Rejected):
            await reconcile()
        if not refund_while_held:
            operation=receipt('charge','charged','2')
            await reconcile()
            await reconcile()
            assert await balance()==(40,0)
            operation=receipt('partial','partial_refund','0.25')
            assert (await reconcile()).startswith('RECONCILIATION_REQUIRED:')
            assert await balance()==(40,0)
            assert await pool.fetchval('SELECT status FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)=='required'
            assert tuple(await pool.fetchrow("SELECT amount,unit FROM task_financial_receipts WHERE operation_id='partial'"))==(Decimal('0.25'),'USD')
            with pytest.raises(Rejected):
                await manually_resolve_no_refund_case(pool,quote.id,reviewer_external_id=100,
                    operation_id='no-refund-after-partial',amount='2',unit='USD',
                    evidence_ref='ticket:FIN-039-PARTIAL')
            assert await pool.fetchval('SELECT quote_id FROM task_financial_reconciliation_queue WHERE quote_id=$1',quote.id)==quote.id
            assert await pool.fetchval("SELECT count(*) FROM task_financial_reconciliation_manual_audit WHERE quote_id=$1 AND action='no_refund_resolution'",quote.id)==0
            operation=receipt('bad-full','full_refund','0.5')
            assert (await reconcile()).startswith('RECONCILIATION_REQUIRED:')
            assert await pool.fetchval("SELECT count(*) FROM task_financial_receipts WHERE operation_id='bad-full'")==0
            assert await balance()==(40,0)
        operation=receipt('full','full_refund','2')
        await asyncio.gather(reconcile(),reconcile())
        assert await balance()==(100,0)
        assert await pool.fetchval('SELECT status FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)=='resolved'
        schema=await pool.fetchval('SELECT current_schema()')
        code="""
import asyncio,asyncpg,os
from decimal import Decimal
from uuid import UUID
from elevenbot.task_receipts import FinancialOperation,reconcile_generation
async def run():
    async with asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],server_settings={'search_path':os.environ['TEST_SCHEMA']}) as pool:
        async def read(remote):
            return FinancialOperation('anymodel',remote,'full','full_refund',Decimal('2'),'USD',
                                      'charge',Decimal('2'),'USD')
        await reconcile_generation(pool,UUID(os.environ['TEST_QUOTE']),{'anymodel':read})
asyncio.run(run())
"""
        source_dir = str(Path(__file__).resolve().parents[1] / 'src')
        pythonpath = os.pathsep.join(filter(None, (source_dir, os.environ.get('PYTHONPATH'))))
        proc=await asyncio.create_subprocess_exec(sys.executable,'-c',code,
            env=os.environ|{'PYTHONPATH':pythonpath,'TEST_SCHEMA':schema,'TEST_QUOTE':str(quote.id)})
        assert await asyncio.wait_for(proc.wait(),20)==0
        await app.handle(event(2,callback=f'amconfirm:{quote.id}'))
        assert await balance()==(100,0) and await app.svc.reconcile()==0
        kinds=await pool.fetch('SELECT kind FROM ledger WHERE task_quote_id=$1 ORDER BY kind',quote.id)
        assert [r['kind'] for r in kinds]==(['task_release','task_reserve'] if refund_while_held
                                            else ['task_capture','task_refund','task_reserve'])
        assert calls==[('POST','/v1/videos/generations'),('GET','/v1/videos/job-1'),('GET','/v1/videos/job-1')]


async def test_manual_reconciliation_records_evidence_without_wallet_credit(env,confirmed_credit):
    from elevenbot.task_receipts import manually_review_case, manually_resolve_no_refund_case
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,
                anymodel_key='fixture',anymodel_video_live=True,interaction_limit=100)
    await confirmed_credit(pool,cfg,user,100)
    app=TelegramApp(pool,cfg,Transport(False))
    async def provider_response(req):
        assert req.method=='POST' and req.url.path=='/v1/videos/generations'
        return httpx.Response(202,json={'request_id':'manual-review-job'},headers={'x-9router-connection-id':'fixture'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider_response)) as http:
        app.anymodel_video=AnyModelVideoPilot(pool,cfg,api=AnyModelVideoProvider(cfg.anymodel_key,client=http))
        app.pricing.adapters['anymodel']=Price()
        quote=await app.pricing.quote(user,Request('anymodel',MODEL,'video','Fixture','Video',default_params('anymodel','video')))
        await app.confirm_price(user,100,quote.id,1)
        for _ in range(100):
            if await pool.fetchval('SELECT 1 FROM task_dispatch WHERE quote_id=$1',quote.id):
                break
            await asyncio.sleep(0.01)
        assert await pool.fetchval('SELECT 1 FROM task_dispatch WHERE quote_id=$1',quote.id)
    assert (await reconcile_generation(pool,quote.id,{})).startswith('RECONCILIATION_REQUIRED:')
    before=tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE mode='live' AND user_id=$1",user))
    with pytest.raises(Rejected):
        await app.price_admin(user,101,'/price_account',
            [str(quote.id),'manual-review','dashboard-op-1','2','USD','ticket:FIN-039-100'])
    result=await manually_review_case(pool,quote.id,reviewer_external_id=100,operation_id='dashboard-op-1',
                                     amount='2',unit='USD',evidence_ref='ticket:FIN-039-100')
    assert result=='manual_review_recorded_no_credit'
    after=tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE mode='live' AND user_id=$1",user))
    assert after==before
    case=await pool.fetchrow("SELECT status,manual_reviewed_at FROM task_financial_reconciliation_cases WHERE quote_id=$1",quote.id)
    assert case['status']=='required' and case['manual_reviewed_at'] is not None
    assert await pool.fetchval('SELECT quote_id FROM task_financial_reconciliation_queue WHERE quote_id=$1',quote.id)==quote.id
    audit=await pool.fetchrow("SELECT operation_id,amount,unit,evidence_ref,reviewer_external_id FROM task_financial_reconciliation_manual_audit WHERE quote_id=$1",quote.id)
    assert tuple(audit)==('dashboard-op-1',Decimal('2'),'USD','ticket:FIN-039-100',100)
    assert await manually_review_case(pool,quote.id,reviewer_external_id=100,operation_id='dashboard-op-1',
                                      amount='2',unit='USD',evidence_ref='ticket:FIN-039-100')=='manual_review_recorded_no_credit'
    with pytest.raises(Rejected):
        await manually_review_case(pool,quote.id,reviewer_external_id=101,operation_id='other-op',
                                   amount='2',unit='USD',evidence_ref='ticket:FIN-039-100')
    with pytest.raises(Rejected):
        await manually_review_case(pool,quote.id,reviewer_external_id=100,operation_id='dashboard-op-1',
                                   amount='3',unit='USD',evidence_ref='ticket:FIN-039-100')
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_refund'",quote.id)==0
    with pytest.raises(Rejected):
        await app.price_admin(user,101,'/price_account',
            [str(quote.id),'no-refund','dashboard-no-refund-1','2','USD','ticket:FIN-039-101'])
    with pytest.raises(Rejected):
        await manually_resolve_no_refund_case(pool,quote.id,reviewer_external_id=100,
            operation_id='dashboard-no-refund-1',amount='2',unit='USD',evidence_ref='ticket:FIN-039-101')
    assert await pool.fetchval('SELECT status FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)=='required'
    assert await pool.fetchval('SELECT quote_id FROM task_financial_reconciliation_queue WHERE quote_id=$1',quote.id)==quote.id
    assert await pool.fetchval("SELECT count(*) FROM task_financial_reconciliation_manual_audit WHERE quote_id=$1 AND action='no_refund_resolution'",quote.id)==0
    await pool.execute("UPDATE video_jobs SET status='succeeded' WHERE id=$1",quote.id)
    await pool.execute("UPDATE task_dispatch SET state='completed' WHERE quote_id=$1",quote.id)
    await settle_task_tokens(pool,quote.id)
    captured=tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE mode='live' AND user_id=$1",user))
    price=int(quote.price['total'])
    assert captured==(before[0],before[1]-price)
    no_refund_args=dict(reviewer_external_id=100,operation_id='dashboard-no-refund-1',
                        amount='2',unit='USD',evidence_ref='ticket:FIN-039-101')
    no_refund=await asyncio.gather(
        manually_resolve_no_refund_case(pool,quote.id,**no_refund_args),
        manually_resolve_no_refund_case(pool,quote.id,**no_refund_args),
    )
    assert no_refund==['no_refund_resolved_no_credit','no_refund_resolved_no_credit']
    assert await pool.fetchval('SELECT status FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)=='resolved_no_refund'
    assert await pool.fetchval('SELECT quote_id FROM task_financial_reconciliation_queue WHERE quote_id=$1',quote.id) is None
    assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE mode='live' AND user_id=$1",user))==captured
    audit_before=await pool.fetch("SELECT operation_id,amount,unit,evidence_ref,reviewer_external_id,action FROM task_financial_reconciliation_manual_audit WHERE quote_id=$1 ORDER BY action",quote.id)
    assert len(audit_before)==2
    async def refund(remote):
        assert remote=='manual-review-job'
        return FinancialOperation('anymodel',remote,'late-refund','full_refund',Decimal('2'),'USD',
                                  'late-charge',Decimal('2'),'USD')
    late=await asyncio.gather(reconcile_generation(pool,quote.id,{'anymodel':refund}),
                              reconcile_generation(pool,quote.id,{'anymodel':refund}))
    assert late==['full_refund','full_refund']
    assert await manually_resolve_no_refund_case(pool,quote.id,reviewer_external_id=100,
        operation_id='no-refund-after-confirmed-refund',amount='2',unit='USD',
        evidence_ref='ticket:FIN-039-102')=='full_refund'
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_refund'",quote.id)==1
    assert await pool.fetchval('SELECT status FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote.id)=='resolved'
    assert await pool.fetch("SELECT operation_id,amount,unit,evidence_ref,reviewer_external_id,action FROM task_financial_reconciliation_manual_audit WHERE quote_id=$1 ORDER BY action",quote.id)==audit_before
    assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE mode='live' AND user_id=$1",user))==(before[0]+price,before[1]-price)
