import asyncio
import json

import httpx
import pytest

from elevenbot.core import Rejected
from elevenbot.pricing import Request
from test_admin_access import event
from test_provider_extensibility import app_with_fixture
from test_ui import Bot


async def test_confirmation_uses_live_wallet_and_server_quote(env,confirmed_credit):
    pool,cfg,_,owner=env
    posts=[]

    async def respond(req):
        if req.method=='GET':
            return httpx.Response(200,json={'amount':60})
        assert req.method=='POST' and req.url.path=='/generate'
        model=json.loads(req.content)['model']
        hold=await pool.fetchrow("""
            SELECT w.available,w.reserved,q.state,d.state AS dispatch_state,l.dr
            FROM ledger l JOIN task_dispatch d ON d.quote_id=l.task_quote_id
            JOIN task_price_quotes q ON q.id=d.quote_id
            JOIN wallets w ON w.user_id=q.user_id AND w.mode='live'
            WHERE q.model_id=$1 AND l.kind='task_reserve'
            """,model)
        assert tuple(hold)==(40,60,'accepted','dispatching',60)
        posts.append(model)
        return httpx.Response(200,json={'answer':'result'})

    async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(respond)) as http:
        bot=Bot()
        app=app_with_fixture(pool,cfg,bot,http)
        other=app_with_fixture(pool,cfg,Bot(),http)
        guest=await app.svc.identity(101)
        await app.svc.accept(guest)
        assert (await app.svc.wallet(guest))['available']==0
        assert (await app.svc.wallet(owner))['available']==0
        await app.pricing.set_rate(owner,100,'fixture_token','1',provider='fixture')
        ids=('fixture/zero','fixture/first','fixture/second')
        await pool.executemany("INSERT INTO approved_models VALUES('fixture',$1,'chat','Model')",
                               [(model,) for model in ids])

        async def quote(user, model):
            return await app.pricing.quote(user,Request('fixture',model,'chat','Model','Prompt'))

        zero=await quote(guest,ids[0])
        await app.handle(event(1,'💳 9\u202f999\u202f999 токенов ≈ 999 ₽',chat=101))
        assert bot.sent[-1][0]=='Кредиты: 0\nЗарезервировано: 0'
        await app.handle(event(2,chat=101,callback=f'amconfirm:{zero.id}'))
        assert bot.sent[-1][0]=='Недостаточно токенов'

        first,second=[await quote(owner,model) for model in ids[1:]]
        await app.handle(event(3,chat=101,callback=f'amconfirm:{first.id}'))
        assert 'Оценка отменена или запрос уже принят.'==bot.sent[-1][0]
        await app.handle(event(4,chat=100,callback=f'amconfirm:{first.id}:1'))
        assert not posts and not await pool.fetchval('SELECT count(*) FROM task_dispatch')
        assert not await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='task_reserve'")

        payment,order=await confirmed_credit(pool,cfg,owner,100)
        assert not await payment.payment(owner,order,100,'XTR','fixture-charge')
        with pytest.raises(Rejected):
            await payment.payment(guest,order,100,'XTR','fixture-charge')
        with pytest.raises(Rejected):
            await payment.payment(owner,order,999,'XTR','fixture-charge')
        assert (await app.svc.wallet(owner))['available']==100
        assert (await app.svc.wallet(guest))['available']==0
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='payment'")==1

        await asyncio.gather(
            app.handle(event(10,chat=100,callback=f'amconfirm:{first.id}')),
            other.handle(event(11,chat=100,callback=f'amconfirm:{second.id}')),
        )
        assert len(posts)==1
        loser=other.bot if posts[0]==ids[1] else bot
        assert loser.sent[-1][0]=='Недостаточно токенов'
        accepted=first if posts[0]==ids[1] else second
        await other.handle(event(12,chat=100,callback=f'amconfirm:{accepted.id}'))
        assert other.bot.sent[-1][0]=='Оценка отменена или запрос уже принят.'
        assert len(posts)==1
        wallet=await app.svc.wallet(owner)
        assert (wallet['available'],wallet['reserved'])==(40,0)
        assert await pool.fetchval('SELECT count(*) FROM task_dispatch')==1
        assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1
        assert [tuple(r) for r in await pool.fetch("""
            SELECT kind,da,dr FROM ledger WHERE task_quote_id IS NOT NULL ORDER BY kind
            """)]==[('task_capture',0,-60),('task_reserve',-60,60)]
        assert await app.svc.reconcile()==0
