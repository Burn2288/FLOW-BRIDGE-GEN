from base64 import b64encode
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx
import pytest

from elevenbot import telegram
from elevenbot.anymodel_pricing import AnyModelPricing
from elevenbot.anymodel import AnyModelProvider, FIBO_MODEL, model_store
from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from elevenbot.progress import TaskProgress
from elevenbot.task_receipts import FinancialOperation, reconcile_generation
from test_anymodel import routes
from test_image_validation import encoded_image
from test_ui import Bot, event

FIBO_TARIFF={'id':FIBO_MODEL,'endpoint':'/v1/images/generations',
             'billing':{'unit':'image','base_tokens':100000,'coefficient':{'output':0.95}}}


@pytest.mark.parametrize('bonus_state',['available','reserved','spent'])
async def test_referral_reward_for_saved_image(env,confirmed_credit,tmp_path,monkeypatch,bonus_state):
    from elevenbot.task_wallet import settle_task_tokens

    reserved_bonus=0 if bonus_state=='available' else 30
    pool,cfg,svc,inviter=env
    code=(await svc.referral_info(inviter))['code']
    user=await svc.identity(101,referral_code=code)
    await svc.accept(user)
    payment_service,payment_id=await confirmed_credit(pool,cfg,user,1000)
    monkeypatch.setenv('RF02_FUNCTIONAL_TEST','YES')
    cfg=replace(cfg,access_mode='private',admin_ids=(101,),anymodel_test_enabled=True,
                anymodel_image_live=True,anymodel_key='fixture-any',interaction_limit=3,
                catalogue_path=str(tmp_path/'models.json'))
    image=encoded_image('PNG')
    tariff={**FIBO_TARIFF,'billing':{'unit':'image','base_tokens':1000,'coefficient':{'output':1}}}

    remotes=iter(('reward-image','reward-image-second'))

    def respond(req):
        if req.url.path=='/v1/models/info':
            return httpx.Response(200,json=tariff)
        if req.url.path=='/v1/models':
            return httpx.Response(200,json={'data':[{'id':FIBO_MODEL,'kind':'image'}]})
        if req.url.path in ('/v1/models/video','/v1/models/tts'):
            return httpx.Response(200,json={'data':[]})
        if req.url.path=='/v1/images/generations':
            return httpx.Response(202,json={'id':next(remotes)},headers={'Retry-After':'0'})
        assert req.url.path in ('/v1/images/generations/reward-image','/v1/images/generations/reward-image-second')
        return httpx.Response(200,json={'data':[{'b64_json':b64encode(image).decode()}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        adapter=AnyModelProvider(cfg.anymodel_key,client=http)
        await adapter.refresh(model_store(cfg))
        monkeypatch.setattr(telegram,'AnyModelProvider',lambda _:adapter)
        bot=Bot()
        bot.send_photo=AsyncMock(return_value=SimpleNamespace(message_id=15))
        app=telegram.TelegramApp(pool,cfg,bot)
        app.anymodel_images.adapter=adapter
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=adapter)
        async def generate(update_id):
            await app.callback(user,101,'amimage:detail')
            await app.callback(user,101,routes(bot)['🖼 Генерировать изображение'])
            payload=event('Draw a blue square').model_dump(by_alias=True,exclude_none=True)
            payload['update_id']=update_id
            payload['message']['chat']['id']=101
            payload['message']['from']['id']=101
            await app.handle(type(event()).model_validate(payload))
            await app.callback(user,101,routes(bot)['Генерировать'],request_id=update_id+1)
            jobs=AnyModelImageJobs(pool,cfg,adapter=adapter)
            await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
            assert await jobs.poll_one(bot)
            assert await jobs.poll_one(bot)
            await asyncio.gather(settle_task_tokens(pool),settle_task_tokens(pool))
        await generate(1)
        reward=await pool.fetchrow("""SELECT r.eligible_paid,r.amount,l.da,f.origin
            FROM referral_rewards r JOIN ledger l ON l.id=r.reward_ledger_id
            JOIN wallet_funding_lots f ON f.credit_ledger_id=l.id WHERE r.referrer_id=$1""",inviter)
        assert reward is not None and tuple(reward)==(1000,50,50,'REFERRAL')
        assert await pool.fetchval('SELECT count(*) FROM referral_rewards')==1
        assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live'",inviter)==50
        if reserved_bonus:
            from elevenbot import providers
            from elevenbot.core import Service
            monkeypatch.setattr(providers,'catalog',lambda _:[{'id':'fixture-voice'}])
            speech=Service(pool,replace(cfg,mode='clodex',access_mode='public',retail_per_char=1,budget=10_000))
            speech_quote,price=await speech.quote(inviter,'x'*reserved_bonus,'fixture-voice')
            assert price==reserved_bonus
            speech_job=await speech.confirm(inviter,speech_quote)
            if bonus_state=='spent':
                from elevenbot.providers import MockProvider
                from elevenbot.worker import Worker
                monkeypatch.setattr('elevenbot.storage.subprocess.run',
                                    lambda *a, **kw: SimpleNamespace(stdout=b'{"format":{"duration":"1"}}'))
                assert await Worker(pool,speech.cfg,MockProvider()).run_one()
                assert await pool.fetchval("SELECT status FROM jobs WHERE id=$1",speech_job)=='succeeded'
                assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='capture'",speech_job)==1
        quote_id=await pool.fetchval("SELECT task_quote_id FROM ledger WHERE user_id=$1 AND kind='task_capture'",user)
        import asyncpg
        with pytest.raises(asyncpg.RaiseError, match='requires its confirmed refund'):
            await pool.execute('''INSERT INTO referral_reversals(capture_id,refund_id,amount,debited,debt_added)
                SELECT capture_id,capture_id,amount,0,amount FROM referral_rewards''')
        assert await pool.fetchval('SELECT count(*) FROM referral_reversals')==0
        async def refund(remote):
            assert remote=='reward-image'
            return FinancialOperation('anymodel',remote,'reward-refund','full_refund',Decimal('2'),'USD',
                                      'reward-charge',Decimal('2'),'USD')
        monkeypatch.delenv('RF02_FUNCTIONAL_TEST')
        assert await asyncio.gather(*(reconcile_generation(pool,quote_id,{'anymodel':refund}) for _ in range(2))) == ['full_refund','full_refund']
        reversal=await pool.fetchrow('SELECT amount,debited,debt_added FROM referral_reversals')
        assert tuple(reversal)==(50,50-reserved_bonus,reserved_bonus)
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='referral_reversal'")==1
        assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",inviter))==(0,30 if bonus_state=='reserved' else 0)
        assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live'",user)==1000
        assert await pool.fetchval('SELECT amount FROM referral_rewards')==50
        assert await svc.reconcile()==0

        if bonus_state=='reserved':
            assert await asyncio.gather(speech.cancel(inviter,speech_job), speech.cancel(inviter,speech_job)) == [True,True]
            with pytest.raises(asyncpg.RaiseError, match='invalid referral restoration event'):
                await pool.execute('''INSERT INTO referral_restoration_repayments
                    SELECT id,user_id,1,gen_random_uuid() FROM ledger WHERE kind='referral_reward' ''')
            restored=await pool.fetchrow("""SELECT p.amount,d.da,r.kind
                FROM referral_restoration_repayments p JOIN ledger d ON d.id=p.ledger_id
                JOIN ledger r ON r.id=p.restoration_id WHERE p.user_id=$1""",inviter)
            assert tuple(restored)==(30,-30,'release')
            assert await pool.fetchval('SELECT outstanding FROM referral_debt_balances WHERE user_id=$1',inviter)==0
            assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",inviter))==(0,0)
            assert await svc.reconcile()==0
        if bonus_state=='spent':
            monkeypatch.setenv('RF02_FUNCTIONAL_TEST','YES')
            await generate(10)
            assert await pool.fetchval('SELECT count(*) FROM referral_rewards')==2
            assert await pool.fetchval('SELECT amount FROM referral_debt_repayments')==30
            assert await pool.fetchval("SELECT da FROM ledger WHERE kind='referral_debt_repay'")==-30
            assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live'",inviter)==20
            assert await pool.fetchval("SELECT sum(available) FROM wallet_funding_lots WHERE user_id=$1 AND origin='REFERRAL'",inviter)==20
            second=await pool.fetchval("SELECT task_quote_id FROM ledger WHERE user_id=$1 AND kind='task_capture' AND task_quote_id<>$2",user,quote_id)
            async def second_refund(remote):
                assert remote=='reward-image-second'
                return FinancialOperation('anymodel',remote,'second-refund','full_refund',Decimal('2'),'USD',
                                          'second-charge',Decimal('2'),'USD')
            assert await asyncio.gather(*(reconcile_generation(pool,second,{'anymodel':second_refund}) for _ in range(2))) == ['full_refund','full_refund']
            assert await pool.fetchval('SELECT count(*) FROM referral_reversals')==2
            assert await pool.fetchval('SELECT sum(debt_added) FROM referral_reversals')==60
            assert await pool.fetchval('SELECT sum(amount) FROM referral_debt_repayments')==30
            from elevenbot.referrals import own_finances
            own = await own_finances(svc, inviter, 0)
            other = await own_finances(svc, user, 0)
            assert (own['invitee_count'],own['available'],own['total_rewards'],own['debt'])==(1,'0','100','30')
            assert len(own['history'])==5 and not own['has_more']
            assert other['history']==[] and other['total_rewards']=='0'
            await payment_service.prepare_refund(payment_id)
            await payment_service.complete_refund(payment_id)
            await asyncio.gather(settle_task_tokens(pool),settle_task_tokens(pool))
            cases=await pool.fetch('SELECT payment_id,affected_funding,reason FROM referral_payment_review_cases')
            assert [tuple(row) for row in cases]==[(payment_id,1000,'payment_refunded')]*2
            report=await svc.reconciliation_report(1)
            assert report['referral_payment_reviews']==2 and report['referral_payment_reviews_truncated']
            detail=report['referral_payment_review_details'][0]
            assert detail['status']=='RECONCILIATION_REQUIRED'
            assert (detail['affected_funding_basis'],detail['eligible_paid_total'],detail['original_reward'],detail['recorded_reversal']) == ('POTENTIAL_ALLOCATION',1000,50,50)
            assert detail['unresolved_reward_amount_status']=='NOT_PROVEN'
            assert await pool.fetchval('SELECT count(*) FROM referral_reversals')==2
            assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live'",inviter)==0
            assert await svc.reconcile()==0


@pytest.mark.parametrize('variant',['base64','corrupt','url','broken','timeout','connect','unsafe',
                                   'refund_before_capture','refund_after_capture','unconfirmed','no_job_id','charged_image'])
async def test_fibo_provider_and_library(funded_env,tmp_path,monkeypatch,capsys,variant):
    pool,cfg,_,user=funded_env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,anymodel_image_live=True,
                anymodel_key='fixture-any',clodex_key='fixture-clodex',catalogue_path=str(tmp_path/'models.json'),
                interaction_limit=3)
    png=encoded_image('PNG')
    damaged=bytearray(png)
    damaged[damaged.index(b'IDAT')+4]^=1
    damaged=bytes(damaged)
    calls=[]

    async def dns(*args,**kwargs):
        return [(2,1,6,'',('93.184.216.34',443))]

    monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',dns)

    def respond(req):
        calls.append((req.method,req.url.path))
        if req.url.path in ('/v1/models/video','/v1/models/tts'):
            return httpx.Response(200,json={'data':[]})
        if req.url.path=='/v1/models/info':
            return httpx.Response(200,json=FIBO_TARIFF)
        if req.url.path=='/v1/models':
            return httpx.Response(200,json={'data':[
                {'id':FIBO_MODEL,'kind':'image'},{'id':'anymedia/fibo-lite','kind':'image'},
            ]})
        if req.url.path=='/v1/images/generations' and req.method=='POST':
            assert req.url.host=='anymodel.org'
            assert req.headers['Authorization']=='Bearer fixture-any'
            assert json.loads(req.content)=={'model':FIBO_MODEL,'prompt':'Draw a blue square','background':True}
            if variant in ('refund_before_capture','refund_after_capture','unconfirmed','charged_image'):
                return httpx.Response(202,json={'id':'image-job-1'},headers={'Retry-After':'0'})
            if variant=='no_job_id':
                return httpx.Response(200,json={'data':[{'b64_json':b64encode(damaged).decode()}]})
            if variant=='timeout':
                raise httpx.ReadTimeout('fixture')
            if variant=='connect':
                raise httpx.ConnectError('fixture')
            if variant in ('url','unsafe'):
                url=('https' if variant=='url' else 'http')+'://images.example/fixture.png'
                return httpx.Response(200,json={'data':[{'url':url}]})
            image=png if variant=='base64' else damaged if variant=='corrupt' else b'{"error":"bad"}'
            return httpx.Response(200,json={'data':[{'b64_json':b64encode(image).decode()}]})
        if req.url.path=='/v1/images/generations/image-job-1' and req.method=='GET':
            assert req.headers['Authorization']=='Bearer fixture-any'
            return httpx.Response(200,json={'data':[{'b64_json':b64encode(damaged).decode()}]})
        assert req.headers['Host']=='images.example'
        assert 'Authorization' not in req.headers
        return httpx.Response(200,content=png)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        await AnyModelProvider(cfg.anymodel_key,client=http).refresh(model_store(cfg))
        monkeypatch.setattr(telegram,'AnyModelProvider',lambda key: AnyModelProvider(key,client=http))
        bot=Bot()
        bot.send_photo=AsyncMock(return_value=SimpleNamespace(message_id=15))
        app=telegram.TelegramApp(pool,cfg,bot)
        wallet_initial=tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user))
        app.anymodel_images.adapter=AnyModelProvider(cfg.anymodel_key,client=http)
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=app.anymodel_images.adapter)
        await app.callback(user,100,'am')
        home=routes(bot)
        assert list(home.values())==['amsection:video','amsection:image','amsection:speech',
                                     'history:0','agmanage:anymodel','providers']
        for section in ('chat','tools'):
            await app.callback(user,100,f'amsection:{section}')
            assert 'пока нет подключённых операций' in bot.sent[-1][0]
        await app.callback(user,100,home['⚙️ Управление агрегатором'])
        await app.callback(user,100,routes(bot)['Все модели'])
        assert 'anymedia/fibo-lite' in routes(bot)
        await app.callback(user,100,'amsection:image')
        assert 'FIBO 2' in routes(bot)
        await app.callback(user,100,routes(bot)['FIBO 2'])
        assert FIBO_MODEL in bot.sent[-1][0]
        run=routes(bot)['🖼 Генерировать изображение']
        disabled=telegram.TelegramApp(pool,replace(cfg,anymodel_image_live=False),Bot())
        await disabled.callback(user,100,'amimage:detail')
        assert run in routes(disabled.bot).values()  # Quotes are available with live runs disabled.
        await app.callback(user,100,run)
        assert 'Пришлите описание' in bot.sent[-1][0]
        prompt=event('Draw a blue square')
        await app.handle(prompt)
        assert '95\u202f000' in bot.sent[-1][0]
        action=routes(bot)['Генерировать']
        assert not any(method=='POST' for method,_ in calls)
        await app.handle(event(callback=action).model_copy(update={'update_id':2}))
        with pytest.raises(telegram.Rejected):
            await app.callback(user,100,action,request_id=3)
        expected_image=damaged if variant=='corrupt' else png
        if variant in ('base64','corrupt','url','refund_before_capture','refund_after_capture','no_job_id','unconfirmed','charged_image'):
            jobs=AnyModelImageJobs(pool,cfg,adapter=AnyModelProvider(cfg.anymodel_key,client=http))
            if variant in ('refund_before_capture','refund_after_capture'):
                await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
            assert await jobs.poll_one(bot)
            if variant in ('refund_before_capture','refund_after_capture','unconfirmed','charged_image'):
                assert await jobs.poll_one(bot)
            bot.send_photo.assert_awaited_once()
            assert bot.send_photo.await_args.args[1].data==(damaged if variant.startswith('refund_') or variant in ('no_job_id','unconfirmed','charged_image') else expected_image)
            await app.callback(user,100,'history:0')
            await app.callback(user,100,routes(bot)['Открыть работу №1'])
            assert bot.send_photo.await_count==2
            assert bot.send_photo.await_args.args[1].data==(damaged if variant.startswith('refund_') or variant in ('no_job_id','unconfirmed','charged_image') else expected_image)
            assert await pool.fetchval('SELECT image FROM image_works')==(damaged if variant.startswith('refund_') or variant in ('no_job_id','unconfirmed','charged_image') else expected_image)
            if variant.startswith('refund_'):
                quote_id=await pool.fetchval('SELECT id FROM task_price_quotes WHERE user_id=$1 ORDER BY accepted_at DESC LIMIT 1',user)
                assert (await reconcile_generation(pool,quote_id,{})).startswith('RECONCILIATION_REQUIRED:')
                if variant=='refund_after_capture':
                    async def lookup(remote):
                        assert remote=='image-job-1'
                        return FinancialOperation('anymodel',remote,'image-charge','charged',Decimal('2'),'USD')
                    assert await reconcile_generation(pool,quote_id,{'anymodel':lookup})=='charged'
                async def refund(remote):
                    assert remote=='image-job-1'
                    return FinancialOperation('anymodel',remote,'image-refund','full_refund',Decimal('2'),'USD',
                                              'image-charge',Decimal('2'),'USD')
                results=await asyncio.gather(reconcile_generation(pool,quote_id,{'anymodel':refund}),
                                             reconcile_generation(pool,quote_id,{'anymodel':refund}))
                assert results==['full_refund','full_refund']
                assert await reconcile_generation(pool,quote_id,{'anymodel':refund})=='full_refund'
                after=tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user))
                assert after==(wallet_initial[0],0)
                kinds=[r['kind'] for r in await pool.fetch('SELECT kind FROM ledger WHERE task_quote_id=$1 ORDER BY kind',quote_id)]
                assert kinds==(['task_release','task_reserve'] if variant=='refund_before_capture'
                               else ['task_capture','task_refund','task_reserve'])
                assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_refund'",quote_id)==(0 if variant=='refund_before_capture' else 1)
                assert await pool.fetchval("SELECT count(*) FROM anymodel_image_jobs WHERE provider_id='image-job-1'")==1
                assert sum(1 for method,path in calls if method=='POST' and path=='/v1/images/generations')==1
            elif variant=='no_job_id':
                quote_id=await pool.fetchval('SELECT id FROM task_price_quotes WHERE user_id=$1 ORDER BY accepted_at DESC LIMIT 1',user)
                price=int(await pool.fetchval("SELECT price->>'total' FROM task_price_quotes WHERE id=$1",quote_id))
                assert (await reconcile_generation(pool,quote_id,{})).startswith('RECONCILIATION_REQUIRED:')
                case=await pool.fetchrow('SELECT provider_job_id,status,finding FROM task_financial_reconciliation_cases WHERE quote_id=$1',quote_id)
                assert tuple(case)==(None,'required','provider_operation_id_unavailable_or_ambiguous')
                assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_refund'",quote_id)==0
                assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user))==(wallet_initial[0]-price,wallet_initial[1])
            elif variant=='unconfirmed':
                quote_id=await pool.fetchval('SELECT id FROM task_price_quotes WHERE user_id=$1 ORDER BY accepted_at DESC LIMIT 1',user)
                price=int(await pool.fetchval("SELECT price->>'total' FROM task_price_quotes WHERE id=$1",quote_id))
                async def lookup(remote):
                    assert remote=='image-job-1'
                    return None
                assert (await reconcile_generation(pool,quote_id,{'anymodel':lookup})).startswith('RECONCILIATION_REQUIRED:')
                assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user))==(wallet_initial[0]-price,wallet_initial[1]+price)
                assert await pool.fetchval("SELECT count(*) FROM image_works WHERE user_id=$1",user)==1
                assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_refund'",quote_id)==0
            elif variant=='charged_image':
                quote_id=await pool.fetchval('SELECT id FROM task_price_quotes WHERE user_id=$1 ORDER BY accepted_at DESC LIMIT 1',user)
                async def lookup(remote):
                    assert remote=='image-job-1'
                    return FinancialOperation('anymodel',remote,'image-charge','charged',Decimal('2'),'USD')
                assert await reconcile_generation(pool,quote_id,{'anymodel':lookup})=='charged'
                available=tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user))
                price=int(await pool.fetchval("SELECT price->>'total' FROM task_price_quotes WHERE id=$1",quote_id))
                assert available==(wallet_initial[0]-price,0)
                assert await pool.fetchval("SELECT count(*) FROM image_works WHERE user_id=$1",user)==1
                assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1 AND kind='task_refund'",quote_id)==0
        else:
            assert 'Автоповтора нет' in bot.sent[-1][0]
            expected='unknown' if variant in ('timeout','connect') else 'failed'
            assert await pool.fetchval('SELECT status FROM anymodel_image_jobs')==expected
            if variant in ('timeout','connect'):
                log=capsys.readouterr().out
                assert ('response_timeout' if variant=='timeout' else 'connect_error') in log
                assert 'Draw a blue square' not in log and 'fixture-any' not in log
            assert await pool.fetchval('SELECT count(*) FROM image_works')==0
            bot.send_photo.assert_not_awaited()

    expected_calls=[('GET','/v1/models'),('GET','/v1/models/video'),('GET','/v1/models/tts'),
                    ('GET','/v1/models/info'),('GET','/v1/models/info'),('POST','/v1/images/generations')]
    if variant=='url': expected_calls.append(('GET','/fixture.png'))
    if variant.startswith('refund_') or variant in ('unconfirmed','charged_image'):
        expected_calls.append(('GET','/v1/images/generations/image-job-1'))
    assert calls==expected_calls

POLL_AFTER_RESTART = r"""
import asyncio
from base64 import b64decode
import hashlib
import os

import asyncpg
import httpx

from elevenbot.anymodel import AnyModelProvider
from elevenbot.anymodel_image_jobs import AnyModelImageJobs
from elevenbot.config import Config

calls=[]
resuming_503=os.environ['FIBO_RESUMING_503']=='1'

def respond(req):
    assert req.method=='GET'
    assert req.url.path=='/v1/images/generations/fixture-job'
    assert req.headers['Authorization']=='Bearer fixture-any'
    calls.append(req.url.path)
    if not resuming_503 and len(calls)==1:
        return httpx.Response(202,headers={'Retry-After':'12'},json={'id':'fixture-job','status':'in_progress'})
    if not resuming_503 and len(calls)==2:
        raise httpx.ReadTimeout('fixture')
    return httpx.Response(200,json={'data':[{'b64_json':os.environ['FIBO_PNG']}]})

class Bot:
    async def send_photo(self,external,media,**kwargs):
        assert external==100
        assert media.data==b64decode(os.environ['FIBO_PNG'])
        print('telegram_sha256='+hashlib.sha256(media.data).hexdigest())

async def main():
    async with asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],min_size=1,
                                   server_settings={'search_path':os.environ['FIBO_SCHEMA']}) as pool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            jobs=AnyModelImageJobs(pool,Config(),adapter=AnyModelProvider('fixture-any',client=http))
            assert not await jobs.poll_one(Bot())
            assert calls==[]
            if not resuming_503:
                await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
                assert await jobs.poll_one(Bot())
                assert await pool.fetchval('SELECT next_at>now()+interval \'10 seconds\' FROM anymodel_image_jobs')
                assert not await jobs.poll_one(Bot())
                await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
                assert await jobs.poll_one(Bot())
                assert await pool.fetchval("SELECT status='pending' AND provider_id='fixture-job' FROM anymodel_image_jobs")
            await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
            assert await jobs.poll_one(Bot())
            assert await jobs.poll_one(Bot())
            assert await pool.fetchval("SELECT status='delivered' FROM anymodel_image_jobs")
            assert len(calls)==(1 if resuming_503 else 3)

asyncio.run(main())
"""


@pytest.mark.parametrize('resuming_503',[False,True],ids=['poll-timeout','poll-503'])
async def test_fibo_202_resumes_in_fresh_process(funded_env,tmp_path,monkeypatch,resuming_503):
    pool,cfg,_,user=funded_env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,anymodel_image_live=True,
                anymodel_key='fixture-any',catalogue_path=str(tmp_path/'models.json'),interaction_limit=3)
    png=encoded_image('PNG')
    requests=[]

    def respond(req):
        requests.append((req.method,req.url.path))
        if req.url.path in ('/v1/models/video','/v1/models/tts'):
            return httpx.Response(200,json={'data':[]})
        if req.url.path=='/v1/models/info':
            return httpx.Response(200,json=FIBO_TARIFF)
        if req.url.path=='/v1/models':
            return httpx.Response(200,json={'data':[{'id':FIBO_MODEL,'kind':'image'}]})
        if req.method=='GET':
            assert resuming_503 and req.url.path=='/v1/images/generations/fixture-job'
            return httpx.Response(503,headers={'Retry-After':'60'})
        assert json.loads(req.content)=={'model':FIBO_MODEL,'prompt':'Blue square','background':True}
        return httpx.Response(202,headers={'Retry-After':'120','Location':'https://untrusted.example/ignore'},
                              json={'id':'fixture-job','status':'queued'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        adapter=AnyModelProvider(cfg.anymodel_key,client=http)
        await adapter.refresh(model_store(cfg))
        monkeypatch.setattr(telegram,'AnyModelProvider',lambda key: adapter)
        before=Bot()
        app=telegram.TelegramApp(pool,cfg,before)
        app.anymodel_images.adapter=adapter
        app.pricing.adapters['anymodel']=AnyModelPricing(cfg.anymodel_key,api=adapter)
        await app.callback(user,100,'am')
        await app.callback(user,100,routes(before)['🎆 Генерировать изображение'])
        await app.callback(user,100,routes(before)['FIBO 2'])
        await app.callback(user,100,routes(before)['🖼 Генерировать изображение'])
        await app.handle(event('Blue square'))
        await app.callback(user,100,routes(before)['Генерировать'],request_id=2)
        assert 'FIBO 2 · Генерирую изображение' in before.sent[-1][0]
    expected_requests=[('GET','/v1/models'),('GET','/v1/models/video'),('GET','/v1/models/tts'),
                       ('GET','/v1/models/info'),('GET','/v1/models/info'),('POST','/v1/images/generations')]
    assert requests==expected_requests
    assert await pool.fetchval("""
        SELECT status='pending' AND provider_id='fixture-job' AND next_at>now()+interval '110 seconds'
        FROM anymodel_image_jobs
        """)
    assert not await pool.fetchval('SELECT count(*) FROM image_works')

    if resuming_503:
        await pool.execute('UPDATE anymodel_image_jobs SET next_at=now()')
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            jobs=AnyModelImageJobs(pool,cfg,adapter=AnyModelProvider(cfg.anymodel_key,client=http))
            assert await jobs.poll_one(before)
        assert await pool.fetchval("""
            SELECT status='pending' AND provider_id='fixture-job'
                AND next_at BETWEEN now()+interval '55 seconds' AND now()+interval '60 seconds'
            FROM anymodel_image_jobs
            """)
        assert requests==expected_requests+[('GET','/v1/images/generations/fixture-job')]

    schema=await pool.fetchval('SELECT current_schema()')
    process=await asyncio.create_subprocess_exec(
        sys.executable,'-c',POLL_AFTER_RESTART,
        env=os.environ|{
            'FIBO_SCHEMA':schema,
            'FIBO_RESUMING_503':str(int(resuming_503)),
            'FIBO_PNG':b64encode(png).decode(),
            'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src'),
        },
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(30):
            stdout,stderr=await process.communicate()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode==0, stderr.decode()
    if not resuming_503:
        assert b'anymodel_image_poll_failed' in stdout and b'response_timeout' in stdout
    assert b'telegram_sha256=' in stdout
    assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1

    bot=Bot()
    bot.send_photo=AsyncMock(return_value=SimpleNamespace(message_id=15))
    restarted=telegram.TelegramApp(pool,cfg,bot)
    await restarted.callback(user,100,'history:0')
    await restarted.callback(user,100,routes(bot)['Открыть работу №1'])
    assert bot.send_photo.await_args.args[1].data==png
    assert await pool.fetchval('SELECT image FROM image_works')==png


@pytest.mark.parametrize('status,headers',[(422,{}),(503,{'X-Should-Retry':'false'})])
@pytest.mark.parametrize('linked',[False,True],ids=['standalone','progress-linked'])
async def test_fibo_final_poll_failure_notifies_the_owner_once(env,status,headers,linked):
    pool,cfg,_,user=env
    cfg=replace(cfg,interaction_limit=1)
    calls=[]

    def respond(req):
        calls.append((req.method,req.url.path))
        if req.method=='POST':
            return httpx.Response(202,headers={'Retry-After':'0'},json={'id':'fixture-final'})
        return httpx.Response(status,headers=headers)

    bot=AsyncMock()
    bot.send_message.return_value=SimpleNamespace(message_id=900)
    progress=TaskProgress(bot,pool)

    async def start_progress(job):
        await progress.start(100,'FIBO 2','images.generate',image_id=job)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        adapter=AnyModelProvider('fixture-any',client=http)
        jobs=AnyModelImageJobs(pool,cfg,adapter=adapter)
        await jobs.submit(user,222,'Blue square',on_accepted=start_progress if linked else None)
        assert bot.send_message.await_count==int(linked)
        bot.send_message.reset_mock()
        assert await jobs.poll_one(bot)
        restarted=TaskProgress(bot,pool)
        await restarted.refresh()
        assert not await AnyModelImageJobs(pool,cfg,adapter=adapter).poll_one(bot)
        await restarted.refresh()

    assert calls==[('POST','/v1/images/generations'),('GET','/v1/images/generations/fixture-final')]
    assert await pool.fetchval("SELECT status='failed' AND provider_id='fixture-final' FROM anymodel_image_jobs")
    assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1
    assert await pool.fetchval('SELECT count(*) FROM image_works')==0
    assert await pool.fetchval('SELECT count(*) FROM task_progress')==0
    if linked:
        bot.send_message.assert_not_awaited()
        bot.edit_message_text.assert_awaited_once_with(
            '⚠️ FIBO 2 · Не удалось завершить задачу.',chat_id=100,message_id=900,
        )
    else:
        bot.send_message.assert_awaited_once()
        chat_id,message=bot.send_message.await_args.args
        assert chat_id==100 and 'Не удалось получить изображение' in message
        bot.edit_message_text.assert_not_awaited()
    bot.send_photo.assert_not_awaited()
