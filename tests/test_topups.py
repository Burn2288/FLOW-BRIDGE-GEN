import asyncio
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest

from elevenbot.core import Rejected, uid
from elevenbot.platega import PlategaConfig, PaymentInvalid
from elevenbot.platega_web import PaymentRouter, create_app
from elevenbot.task_wallet import check_task_balance
from elevenbot.topups import CheckoutClient, Topups, amount
from elevenbot.topup_ui import TOPUP_MENU
from elevenbot.telegram import MENU, TelegramApp
from test_admin_access import event
from test_broadcasts import BroadcastTransport, routes


@pytest.fixture
def admin_already_signed_in():
    pass


MERCHANT=str(UUID(int=1001))
SECRET='fixture-only'


class Gateway:
    def __init__(self):
        self.orders={}
        self.posts=[]
        self.exports=0
        self.drop_response=False
        self.currency='RUB'
        self.merchant=MERCHANT
        self.override_amount=None
        self.states={}
        self.refunds={}

    def handler(self,req):
        assert req.headers['X-MerchantId']==MERCHANT
        assert req.headers['X-Secret']==SECRET
        if req.url.path=='/transaction/process':
            payload=json.loads(req.content,parse_float=Decimal)
            order=payload['payload']
            assert payload['metadata']['user_email']=='100@telegram.org'
            assert payload['metadata']['userId']=='100'
            assert order not in self.orders
            remote=str(uuid4())
            self.orders[order]={'remote':remote,'payload':payload}
            self.posts.append(order)
            if self.drop_response:
                raise httpx.ReadTimeout('lost reply',request=req)
            return httpx.Response(200,json={'transactionId':remote,'redirect':'https://pay.platega.io/test',
                                           'expiresIn':'00:15:00','merchantId':MERCHANT})
        if req.url.path=='/transaction/export/json':
            self.exports+=1
            return httpx.Response(200,json=[{'recordId':row['remote'],'payload':key} for key,row in self.orders.items()])
        remote=req.url.path.rsplit('/',1)[-1]
        key,row=next((key,row) for key,row in self.orders.items() if row['remote']==remote)
        data={'id':remote,'payload':key,'status':self.states.get(key,'CONFIRMED'),
              'mechantId':self.merchant,'paymentDetails':{
                  'amount':float(row['payload']['paymentDetails']['amount']) if self.override_amount is None else self.override_amount,
                  'currency':self.currency}}
        if key in self.refunds:
            data['refundedAmount']=self.refunds[key]
        return httpx.Response(200,json=data)

    def event(self,order,status='CONFIRMED'):
        row=self.orders[str(order)]
        return json.dumps({'id':row['remote'],'payload':str(order),'amount':float(row['payload']['paymentDetails']['amount']),
                           'currency':'RUB','status':status}).encode()


async def fixture(env):
    pool,cfg,svc,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),admin_password='fixture-password',
                topup_mode='test',platega_merchant=MERCHANT,platega_secret=SECRET)
    pc=PlategaConfig(merchant=MERCHANT,secret=SECRET,enabled=True,
                    return_url='https://t.me/test_bot?start=pay_{order_id}',failed_url='https://example.org/fail')
    gateway=Gateway()
    client=CheckoutClient(pc,httpx.AsyncClient(transport=httpx.MockTransport(gateway.handler)))
    payments=Topups(pool,cfg,client)
    from elevenbot.pricing import Pricing
    await Pricing(pool,cfg,{}).set_ruble_rate(user,100,'100','10')
    return pool,cfg,user,payments,gateway


async def quote(payments,user,key=None,minor=10000):
    return await payments.quote(user,100,minor,key or uuid4().hex[:12],test_session=True)


@pytest.mark.parametrize('text,expected',[('50',5000),('100,25',10025),('10.01',1001)])
def test_topup_amount(text,expected):
    assert amount(text)==expected


@pytest.mark.parametrize('text',['0','-1','nan','1e2','0.001','1.2.3','5 000',''])
def test_topup_invalid_amount(text):
    with pytest.raises(Rejected):
        amount(text)


async def test_topup_idempotency_rate_snapshot_and_test_wallet(env):
    pool,cfg,user,payments,gateway=await fixture(env)
    before=await pool.fetchrow("SELECT * FROM wallets WHERE user_id=$1 AND mode='demo'",user)
    real=await pool.fetchrow("SELECT * FROM wallets WHERE user_id=$1 AND mode='live'",user)
    order=await quote(payments,user,'a'*12)
    assert order['credits']==1000
    assert (await quote(payments,user,'a'*12))['id']==order['id']
    await pool.execute('UPDATE task_ruble_equivalent SET rubles=20 WHERE id=1')
    await asyncio.gather(*(payments.create(user,order['id'],test_session=True) for _ in range(10)))
    assert len(gateway.posts)==1
    callback=gateway.event(order['id'])
    headers={'X-MerchantId':MERCHANT,'X-Secret':SECRET}
    await asyncio.gather(payments.callback(headers,callback),payments.check(user,order['id']),
                         payments.callback(headers,callback))
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='topup'")==1
    assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='demo'",user)==before['available']+1000
    assert real==await pool.fetchrow("SELECT * FROM wallets WHERE user_id=$1 AND mode='live'",user)
    assert (await payments.owned(user,order['id']))['state']=='paid'
    other=await payments.svc.identity(101)
    with pytest.raises(Rejected):
        await payments.check(other,order['id'])
    bad=callback
    with pytest.raises(PermissionError):
        await payments.callback({},bad)
    bot=BroadcastTransport(pool)
    await payments.notify(bot)
    await Topups(pool,cfg,payments.client).notify(bot)
    assert len([s for s in bot.messages.values() if 'Баланс пополнен' in s[1]])==1
    await payments.client.close()


@pytest.mark.parametrize('kind',['amount','currency','merchant'])
async def test_topup_mismatch_mints_nothing(env,kind):
    pool,cfg,user,payments,gateway=await fixture(env)
    row=await quote(payments,user)
    await payments.create(user,row['id'],test_session=True)
    if kind=='amount':gateway.override_amount=101
    if kind=='currency':gateway.currency='USD'
    if kind=='merchant':gateway.merchant=str(UUID(int=1002))
    with pytest.raises(PaymentInvalid):
        await payments.check(user,row['id'])
    assert not await pool.fetchval("SELECT EXISTS(SELECT 1 FROM ledger WHERE kind='topup')")
    await payments.client.close()


async def test_topup_creation_unknown_recovers_without_second_post(env):
    pool,cfg,user,payments,gateway=await fixture(env)
    row=await quote(payments,user)
    gateway.drop_response=True
    with pytest.raises(Rejected):
        await payments.create(user,row['id'],test_session=True)
    restarted=Topups(pool,cfg,payments.client)
    await restarted.create(user,row['id'],test_session=True)
    assert len(gateway.posts)==1
    await restarted.check(user,row['id'])
    assert len(gateway.posts)==1 and gateway.exports==1
    assert (await restarted.owned(user,row['id']))['state']=='paid'
    await payments.client.close()


async def test_topup_refunds_debt_and_concurrent_spending(env):
    pool,cfg,user,payments,gateway=await fixture(env)
    row=await quote(payments,user)
    await payments.create(user,row['id'],test_session=True)
    await payments.check(user,row['id'])
    # Consume demo funds through the ordinary generation reservation.
    svc=payments.svc
    cost=await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='demo'",user)
    cfg=replace(cfg,access_mode='public',generation_enabled=True,retail_per_char=cost,cost_per_char=1)
    from elevenbot.core import Service
    svc=Service(pool,cfg)
    proposal,_=await svc.quote(user,'x','demo')
    await svc.confirm(user,proposal)
    gateway.states[str(row['id'])]='PARTIALLY_REFUNDED'
    gateway.refunds[str(row['id'])]=25
    await asyncio.gather(payments.check(user,row['id']),payments.check(user,row['id']))
    assert await pool.fetchval("SELECT amount FROM wallet_debts WHERE user_id=$1 AND mode='demo'",user)==250
    gateway.states[str(row['id'])]='CHARGEBACKED'
    await payments.check(user,row['id'])
    assert await pool.fetchval("SELECT amount FROM wallet_debts WHERE user_id=$1 AND mode='demo'",user)==1000
    assert await pool.fetchval('SELECT count(*) FROM topup_adjustments')==2
    assert await pool.fetchval("SELECT reserved FROM wallets WHERE user_id=$1 AND mode='demo'",user)==cost
    second=await quote(payments,user)
    await payments.create(user,second['id'],test_session=True)
    await payments.check(user,second['id'])
    assert await pool.fetchval("SELECT amount FROM wallet_debts WHERE user_id=$1 AND mode='demo'",user)==0
    assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='demo'",user)==0
    await payments.client.close()


@pytest.mark.parametrize('state',['CANCELED','PENDING'])
async def test_topup_cancel_expiry_and_late_payment(env,state):
    pool,cfg,user,payments,gateway=await fixture(env)
    row=await quote(payments,user)
    await payments.create(user,row['id'],test_session=True)
    await pool.execute("UPDATE topup_orders SET expires_at=now()-interval '1 hour' WHERE payment_id=$1",row['id'])
    gateway.states[str(row['id'])]=state
    await payments.check(user,row['id'])
    assert (await payments.owned(user,row['id']))['state']==('cancelled' if state=='CANCELED' else 'expired')
    assert not await pool.fetchval("SELECT EXISTS(SELECT 1 FROM ledger WHERE kind='topup')")
    gateway.states[str(row['id'])]='CONFIRMED'
    await payments.tick()
    assert (await payments.owned(user,row['id']))['state']=='paid'
    await payments.client.close()


async def test_topup_ui_and_admin_isolation(env):
    pool,cfg,user,payments,gateway=await fixture(env)
    app=TelegramApp(pool,cfg,BroadcastTransport(pool))
    app.topups=payments
    app.topup_ui.payments=payments
    n=0
    async def send(text=None,callback=None,chat=100):
        nonlocal n
        n+=1
        await app.handle(event(n,text,callback=callback,chat=chat))
        active=(await app.navigation.read(chat)).active_id
        return app.bot.messages.get(active)
    await send('/admin')
    await send(cfg.admin_password)
    admin=await send(callback='tuadmin')
    assert 'Предпросмотр' in routes(admin)
    await send(callback='tuadd')
    await send('350,50')
    assert await pool.fetchval('SELECT count(*) FROM topup_presets')==4
    panel=await send(TOPUP_MENU)
    assert '350.5 ₽ · 3 505 токенов' in routes(panel)
    own=routes(panel)['✏️ Своя сумма']
    await send(callback=own)
    order=await send('100,00')
    assert 'Будет зачислено 1 000 токенов' in order[1]
    created=await send(callback=routes(order)['Перейти к оплате'])
    assert created[2].inline_keyboard[0][0].url=='https://pay.platega.io/test'
    await send(callback=routes(created)['Проверить оплату'])
    assert len(gateway.posts)==1
    await payments.notify(app.bot)
    posts={ident for ident,screen in app.bot.messages.items() if 'Баланс пополнен' in screen[1]}
    assert len(posts)==1
    await send(MENU[0])
    await send(MENU[1])
    assert posts <= app.bot.messages.keys()
    await send('/admin_logout')
    await send(callback='tuadmin')
    assert app.bot.answers[-1][1]['text']=='Войдите через /admin.'
    await payments.client.close()




async def test_topup_rollback_during_credit_and_two_independent_orders(env,monkeypatch):
    pool,cfg,user,payments,gateway=await fixture(env)
    first,second=await quote(payments,user),await quote(payments,user)
    await asyncio.gather(*(payments.create(user,r['id'],test_session=True) for r in (first,second)))
    from elevenbot.core import Service
    movement=Service.movement
    async def fail_after_insert(self,*args,**kwargs):
        await movement(self,*args,**kwargs)
        raise RuntimeError('fixture crash before commit')
    monkeypatch.setattr(Service,'movement',fail_after_insert)
    with pytest.raises(RuntimeError):
        await payments.check(user,first['id'])
    assert not await pool.fetchval("SELECT EXISTS(SELECT 1 FROM ledger WHERE kind='topup')")
    monkeypatch.setattr(Service,'movement',movement)
    restarted=Topups(pool,cfg,payments.client)
    await asyncio.gather(restarted.check(user,first['id']),restarted.check(user,second['id']))
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='topup'")==2
    assert len(gateway.posts)==2
    await payments.client.close()


async def test_live_wallet_topup_and_generation_share_atomic_balance(env,monkeypatch):
    pool,cfg,user,payments,gateway=await fixture(env)
    cfg=replace(cfg,topup_mode='live',payments_enabled=True,platega_enabled=True)
    payments=Topups(pool,cfg,payments.client)
    first=await quote(payments,user)
    await payments.create(user,first['id'])
    await payments.check(user,first['id'])
    from test_provider_extensibility import app_with_fixture
    from test_ui import Bot
    from elevenbot.pricing import Request
    posts=[]
    def generation(req):
        if req.method=='GET':return httpx.Response(200,json={'amount':600})
        posts.append(req.method)
        return httpx.Response(200,json={'answer':'fixture result'})
    async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(generation)) as c:
        app=app_with_fixture(pool,replace(cfg,payments_enabled=False),Bot(),c)
        await app.pricing.set_rate(user,100,'fixture_token','1',provider='fixture')
        await pool.execute("INSERT INTO approved_models VALUES('fixture','fixture/chat','chat','Chat')")
        proposal=await app.pricing.quote(user,Request('fixture','fixture/chat','chat','Chat','Hello'))
        second=await quote(payments,user)
        await payments.create(user,second['id'])
        await asyncio.gather(payments.check(user,second['id']),
            app.callback(user,100,'amconfirm:'+str(proposal.id),request_id=550))
        wallet=await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user)
        assert tuple(wallet)==(1400,0) and posts==['POST']
        gateway.states[str(first['id'])]='CHARGEBACKED'
        await payments.check(user,first['id'])
        gateway.states[str(second['id'])]='CHARGEBACKED'
        await payments.check(user,second['id'])
        assert await pool.fetchval("SELECT amount FROM wallet_debts WHERE user_id=$1 AND mode='live'",user)==600
        async with pool.acquire() as conn,conn.transaction():
            with pytest.raises(Rejected,match='Расходы ограничены'):
                await check_task_balance(conn,user,1)
    await payments.client.close()


async def test_topup_webhook_button_race_and_tampered_callback(env):
    from aiohttp import web, ClientSession
    pool,cfg,user,payments,gateway=await fixture(env)
    row=await quote(payments,user)
    await payments.create(user,row['id'],test_session=True)
    app=create_app(PaymentRouter(pool,cfg,payments.client))
    runner=web.AppRunner(app,access_log=None)
    await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0)
    await site.start()
    port=site._server.sockets[0].getsockname()[1]
    headers={'X-MerchantId':MERCHANT,'X-Secret':SECRET}
    try:
        async with ClientSession() as http:
            url=f'http://127.0.0.1:{port}/payments/platega/callback'
            async with http.post(url,data=gateway.event(row['id'])) as response:
                assert response.status==401
            tampered=json.loads(gateway.event(row['id']))
            tampered['amount']=101
            async with http.post(url,json=tampered,headers=headers) as response:
                assert response.status==400
            async def callback():
                async with http.post(url,data=gateway.event(row['id']),headers=headers) as response:
                    assert response.status==200
            await asyncio.gather(callback(),payments.check(user,row['id']),callback())
            assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='topup'")==1
    finally:
        await runner.cleanup()
        await payments.client.close()


async def test_topup_presets_limits_and_session_isolation(env):
    pool,cfg,user,payments,gateway=await fixture(env)
    cfg=replace(cfg,topup_mode='off')
    app=TelegramApp(pool,cfg,BroadcastTransport(pool))
    other=await app.svc.identity(101)
    await app.svc.accept(other)
    before=await app.svc.conversation(other)
    n=0
    async def send(text=None,callback=None,chat=100):
        nonlocal n
        n+=1
        await app.handle(event(n,text,callback=callback,chat=chat))
        active=(await app.navigation.read(chat)).active_id
        return app.bot.messages.get(active)
    await send('/admin')
    await send(cfg.admin_password)
    for minor in range(1,15):
        await pool.execute('INSERT INTO topup_presets(amount,position) VALUES($1,$2)',minor*5000,minor+30)
    panel=await send(callback='tupresets:0')
    assert 'Далее →' in routes(panel)
    label=next(k for k in routes(panel) if k.endswith('вкл'))
    editor=await send(callback=routes(panel)[label])
    disabled=routes(editor)['Включить / выключить']
    chosen=uid(disabled.split(':')[1])
    await send(callback=disabled)
    assert not await pool.fetchval('SELECT enabled FROM topup_presets WHERE id=$1',chosen)
    original=[r['id'] for r in await pool.fetch('SELECT id FROM topup_presets ORDER BY position,id')]
    await send(callback=f'tumove:{chosen}:down')
    ordered=await pool.fetch('SELECT id FROM topup_presets ORDER BY position,id')
    assert ordered[original.index(chosen)+1]['id']==chosen
    await send(callback=f'tudelete:{chosen}')
    assert not await pool.fetchval('SELECT 1 FROM topup_presets WHERE id=$1',chosen)
    await send(callback='tulimits')
    await send('1 500')
    with pytest.raises(Rejected):
        await app.topups.quote(user,100,99,'b'*12)
    await send(callback='tucustom')
    panel=await send(TOPUP_MENU)
    assert '✏️ Своя сумма' not in routes(panel)
    assert tuple(before)==tuple(await app.svc.conversation(other))
    assert not any('✅ Баланс' in message[1] for message in app.bot.messages.values())
    await send('/admin_logout')
    prior=await pool.fetchval('SELECT custom_enabled FROM topup_settings WHERE id=1')
    await send(callback='tucustom')
    assert prior==await pool.fetchval('SELECT custom_enabled FROM topup_settings WHERE id=1')
    await payments.client.close()



async def test_topup_notice_waits_for_payment_review(env):
    pool,cfg,user,payments,gateway=await fixture(env)
    row=await quote(payments,user)
    await payments.create(user,row['id'],test_session=True)
    await payments.check(user,row['id'])
    gateway.states[str(row['id'])]='DISPUTED'
    await payments.check(user,row['id'])
    bot=BroadcastTransport(pool)
    await payments.notify(bot)
    assert not bot.messages
    gateway.states[str(row['id'])]='CONFIRMED'
    await payments.check(user,row['id'])
    await payments.notify(bot)
    assert len(bot.messages)==1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='topup'")==1
    await payments.client.close()
