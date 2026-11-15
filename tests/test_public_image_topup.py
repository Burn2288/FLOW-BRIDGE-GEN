from dataclasses import replace
import httpx
from elevenbot.topups import Topups
from elevenbot.pricing import Request
from test_topups import fixture
from test_provider_extensibility import FixtureAggregator, app_with_fixture
from unittest.mock import AsyncMock
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.task_launch import Outcome
from types import SimpleNamespace
from test_ui import Bot
from test_admin_access import event

async def test_funded_regular_user_with_one_config(env, monkeypatch):
    pool,cfg,admin,payments,gateway=await fixture(env)
    cfg=replace(cfg,topup_mode='live',payments_enabled=True,platega_enabled=True,
                public_image_models=('fixture:fixture/image',))
    gateway_original=gateway.handler
    def checkout(req):
        if req.url.path=='/transaction/process':
            import json
            from uuid import uuid4
            payload=json.loads(req.content)
            key=payload['payload']
            assert payload['metadata']['userId']=='101'
            remote=str(uuid4())
            gateway.orders[key]={'remote':remote,'payload':payload}
            return httpx.Response(200,json={'transactionId':remote,'redirect':'https://pay.platega.io/test','expiresIn':'00:15:00','merchantId':payments.client.cfg.merchant})
        return gateway_original(req)
    async with httpx.AsyncClient(transport=httpx.MockTransport(checkout)) as payment_http:
        from elevenbot.topups import CheckoutClient
        posts=[]
        def generation(req):
            if req.method=='GET': return httpx.Response(200,json={'amount':600})
            posts.append(req.method)
            return httpx.Response(200,content=MOCK_IMAGE)
        async def prepare(self, conn, user, external, quote, request_id):
            assert quote.request.operation=='images.generate' and external==101

        async def run(self, user, quote, request_id, prepared, on_accepted):
            response=await self.client.post('/generate',json={'model':quote.request.model})
            work=await app.svc.save_image_work(user,request_id,quote.request.model,quote.request.prompt,
                                               SimpleNamespace(image=response.content,filename='test.png'))
            return Outcome('image',work)

        monkeypatch.setattr(FixtureAggregator,'prepare',prepare)
        monkeypatch.setattr(FixtureAggregator,'run',run)
        async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(generation)) as c:
            bot=Bot()
            bot.send_photo=AsyncMock()
            app=app_with_fixture(pool,cfg,bot,c)
            app.topups=Topups(pool,app.cfg,CheckoutClient(payments.client.cfg,payment_http))
            user=await app.svc.identity(101)
            await app.svc.accept(user)
            async def wallet():
                return tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user))
            before=await wallet()
            order=await app.topups.quote(user,101,10000,'abcdef123456')
            await app.topups.create(user,order['id'])
            await app.topups.check(user,order['id'])
            await app.topups.check(user,order['id'])
            funded=await wallet()
            await app.pricing.set_rate(admin,100,'fixture_token','1',provider='fixture')
            await pool.execute("INSERT INTO approved_models VALUES('fixture','fixture/image','images.generate','Image')")
            q=await app.pricing.quote(user,Request('fixture','fixture/image','images.generate','Image','Hello'))
            await app.handle(event(550,chat=101,callback='amconfirm:'+str(q.id)))
            await app.handle(event(551,chat=101,callback='amconfirm:'+str(q.id)))
            after=await wallet()
            ledger=await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1",user)
            status=await pool.fetchval("SELECT status FROM payments WHERE id=$1",order['id'])
            print('ORDER',status,'LEDGER',ledger)
            print('FIXED_CONFIG',before,funded,after,'posts',len(posts),'payments',app.cfg.payments_enabled,'responses',[x[0] for x in bot.sent])
            works=await app.svc.history(user)
            assert before==(0,0) and funded==(1000,0) and after==(400,0)
            assert len(posts)==1 and status=='succeeded' and ledger==3
            assert len(works)==1 and works[0]['kind']=='image'
            assert (await app.svc.image_work(user,works[0]['id']))['image']==MOCK_IMAGE
            assert bot.send_photo.await_count==1 and app.cfg.payments_enabled
    await payments.client.close()
