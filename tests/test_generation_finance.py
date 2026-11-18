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
from elevenbot.task_receipts import FinancialOperation, reconcile_generation
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
        app.providers.financial_sources['anymodel']=financial_lookup
        async def reconcile():
            return await reconcile_generation(pool,quote.id,{'anymodel':financial_lookup})
        def receipt(key,outcome,amount,remote='job-1'):
            return FinancialOperation('anymodel',remote,key,outcome,Decimal(amount),'USD')

        assert await app.anymodel_video.poll_one(bot)
        assert await reconcile()=='возврат агрегатора не подтверждён'
        operation=TimeoutError()
        await app.handle(event(8,text=f'/price_account {quote.id}'))
        assert await balance()==(40,60)
        operation=None
        if not refund_while_held:
            operation=receipt('charge','charged','2')
            await app.handle(event(9,text=f'/price_account {quote.id}'))
            assert await balance()==(40,0)
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
            await reconcile()
            assert await balance()==(40,0)
            assert tuple(await pool.fetchrow("SELECT amount,unit FROM task_financial_receipts WHERE operation_id='partial'"))==(Decimal('0.25'),'USD')
        operation=receipt('full','full_refund','2')
        await asyncio.gather(reconcile(),reconcile())
        assert await balance()==(100,0)
        schema=await pool.fetchval('SELECT current_schema()')
        code="""
import asyncio,asyncpg,os
from decimal import Decimal
from uuid import UUID
from elevenbot.task_receipts import FinancialOperation,reconcile_generation
async def run():
    async with asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],server_settings={'search_path':os.environ['TEST_SCHEMA']}) as pool:
        async def read(remote):
            return FinancialOperation('anymodel',remote,'full','full_refund',Decimal('2'),'USD')
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
