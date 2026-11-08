import asyncio
from collections import Counter
from contextlib import nullcontext
from dataclasses import replace
import json
from math import ceil
import os
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
from decimal import Decimal

import httpx
import pytest

from elevenbot.aggregate import ProviderRegistry
from elevenbot.core import Rejected
from elevenbot.pricing import PriceUnavailable, ProviderCost, Request
from elevenbot.task_launch import Outcome, notify_interrupted
from elevenbot.telegram import TelegramApp
from test_anymodel import routes
from test_ui import Bot, event


class FixtureAggregator:
    """Third provider transport stays entirely in the acceptance harness."""

    def __init__(self,pool,client):
        self.pool,self.client = pool,client

    async def collect(self):
        response=await self.client.get('/catalogue')
        response.raise_for_status()
        return response.json()

    async def cost(self,request):
        try:
            response=await self.client.get('/price',params={'model':request.model})
            response.raise_for_status()
        except httpx.HTTPError:
            raise PriceUnavailable() from None
        amount=Decimal(response.json()['amount'])
        return ProviderCost(amount,'anymodel_balance_token',True,'fixture /price','1 запрос')

    def background(self,operation):
        return None

    async def prepare(self,conn,user,external,quote,update_id):
        if quote.request.operation!='chat':
            raise Rejected('Операция заглушки недоступна.')

    async def run(self,user,quote,update_id,prepared,on_accepted):
        response=await self.client.post('/generate',json={'model':quote.request.model,'prompt':quote.request.prompt})
        response.raise_for_status()
        answer=response.json()['answer']
        await self.pool.execute('INSERT INTO task_chat_works(quote_id,answer) VALUES($1,$2)',quote.id,answer)
        return Outcome('chat',answer)


def app_with_fixture(pool,cfg,bot,client):
    adapter=FixtureAggregator(pool,client)
    registry=ProviderRegistry()
    registry.register('fixture',adapter,price=adapter,launch=adapter,title='Fixture provider')
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),interaction_limit=100)
    return TelegramApp(pool,cfg,bot,providers=registry)


async def test_third_provider_catalogue_and_tariff_preview(env):
    pool,cfg,_,user=env
    model='fixture/chat'
    requests=Counter()

    def respond(req):
        path=req.url.path
        requests[path]+=1
        if path=='/catalogue':
            return httpx.Response(200,json={'scope':'key_available','functions':[],'models':[
                {'id':model,'title':'Fixture chat','availability':'key_available','operations':['chat'],
                 'capabilities_known':True,'defaults':{'chat':{'max_tokens':128}}},
            ]})
        if path=='/price':
            return httpx.Response(200,json={'amount':100})
        assert req.method=='POST' and json.loads(req.content)=={'model':model,'prompt':'Hello'}
        return httpx.Response(200,json={'answer':'Fixture result'})

    async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(respond)) as http:
        bot=Bot()
        app=app_with_fixture(pool,cfg,bot,http)
        await app.show_providers(100)
        await app.callback(user,100,routes(bot)['Тарифы моделей'])
        await app.callback(user,100,routes(bot)['Fixture provider'])
        await app.callback(user,100,routes(bot)['Fixture chat'])
        await app.callback(user,100,routes(bot)['Чат'])
        assert 'Действующий источник: API' in bot.sent[-1][0]
        await app.callback(user,100,routes(bot)['max_tokens · 128'])
        await app.callback(user,100,routes(bot)['Задать ручную ставку'])
        code=(await app.svc.aggregate_context(user))['tariff_admin']['code']
        await app.pricing.set_rule(user,100,'fixture',model,'percent','25')
        await app.price_admin(user,100,'/tariff_set',[code,'request','anymodel_balance_token','80','fixture-source'])
        assert all(s in bot.sent[-1][0] for s in ('Предпросмотр',model,'80','без срока','100 токенов'))
        assert not await pool.fetchval('SELECT count(*) FROM task_manual_tariffs')
        await app.callback(user,100,routes(bot)['Сохранить ставки'])
        assert await pool.fetchval('SELECT amount FROM task_manual_tariffs')==80
        await app.show_providers(100)
        await app.callback(user,100,routes(bot)['Fixture provider'])
        await app.callback(user,100,routes(bot)['Fixture chat'])
        await app.callback(user,100,routes(bot)['Рассчитать стоимость · Диалог'])
        await app.handle(event('Hello'))
        assert 'Оценка: 125' in bot.sent[-1][0] and requests['/generate']==0
        confirm=routes(bot)['Генерировать']
        await app.callback(user,100,confirm,request_id=2)
        with pytest.raises(Rejected):
            await app.callback(user,100,confirm,request_id=3)
        assert requests['/generate']==1
        assert 'Fixture result' in bot.sent[-1][0]
        await app.callback(user,100,'history:0')
        await app.callback(user,100,routes(bot)['Открыть работу №1'])
        assert 'Fixture result' in bot.sent[-1][0]


async def test_confirmation_load_and_provider_failures(env):
    pool,cfg,_,user=env
    prices=Counter()
    posts=Counter()
    changed=asyncio.Event()
    release=asyncio.Event()
    active=False
    new_rate=100
    faults={'fixture/30':'429','fixture/31':'timeout'}

    async def respond(req):
        if req.url.path=='/price':
            model=req.url.params['model']
            prices[model]+=1
            if active and model=='fixture/29' and not release.is_set():
                changed.set()
                await release.wait()
            await asyncio.sleep(0.01)
            if active and faults.get(model)=='429':
                return httpx.Response(429)
            if active and faults.get(model)=='timeout':
                await asyncio.sleep(0.03)
                raise httpx.ReadTimeout('fixture')
            amount=new_rate if model=='fixture/29' else 100
            return httpx.Response(200,json={'amount':amount})
        assert req.method=='POST' and req.url.path=='/generate'
        model=json.loads(req.content)['model']
        posts[model]+=1
        return httpx.Response(200,json={'answer':'result'})

    async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(respond)) as http:
        app=app_with_fixture(pool,cfg,Bot(),http)
        quotes=[await app.pricing.quote(user,Request('fixture',f'fixture/{i}','chat','Model','Prompt'))
                for i in range(32)]
        assert sum(prices.values())==32 and not posts
        active=True
        latencies=[]
        async def confirm(quote,update,record=False):
            start=perf_counter()
            try:
                _,accepted,_=await app.launch.confirm(user,100,quote.id,update,
                    progress=lambda _:nullcontext(),background=None)
                return 'accepted' if accepted else 'requote'
            except PriceUnavailable:
                return 'price_unavailable'
            except Rejected:
                return 'duplicate'
            finally:
                if record:
                    latencies.append((perf_counter()-start)*1000)

        first=[asyncio.create_task(confirm(q,i+10,True)) for i,q in enumerate(quotes)]
        duplicate=[asyncio.create_task(confirm(quotes[0],100+i)) for i in range(20)]
        try:
            await asyncio.wait_for(changed.wait(),timeout=5)
            new_rate=120
            await app.pricing.set_rule(user,100,'fixture','fixture/29','percent','25')
        finally:
            release.set()
        outcomes=await asyncio.gather(*first,*duplicate)
        assert Counter(outcomes)=={'accepted':29,'requote':1,'price_unavailable':2,'duplicate':20}
        assert sum(prices.values())==64
        assert len(posts)==29 and set(posts.values())=={1}
        assert not any(posts[f'fixture/{i}'] for i in (29,30,31))
        accepted=await pool.fetch("""
            SELECT q.price->>'total' AS total,d.state FROM task_price_quotes q
            JOIN task_dispatch d ON d.quote_id=q.id WHERE q.state='accepted'
            """)
        assert len(accepted)==29 and all(r['total']=='100' and r['state']=='completed' for r in accepted)
        pending=await pool.fetchval("""
            SELECT id FROM task_price_quotes WHERE model_id='fixture/29' AND state='pending' AND price->>'total'='150'
            """)
        assert pending
        print(json.dumps({
            'phase':'parallel','distinct':32,'duplicate_clicks':20,'price_gets_total':sum(prices.values()),
            'price_gets_confirm':sum(prices.values())-32,'generation_posts':sum(posts.values()),
            'outcomes':dict(Counter(outcomes)),'provider_errors':['429','timeout'],
            'confirm_ms_p50':round(median(latencies),2),
            'confirm_ms_p95':round(sorted(latencies)[ceil(0.95*len(latencies))-1],2),
            'confirm_ms_max':round(max(latencies),2),
        }),flush=True)
        faults.clear()
        retries=await asyncio.gather(
            confirm(replace(quotes[29],id=pending),201),confirm(quotes[30],202),confirm(quotes[31],203),
        )
        assert retries==['accepted']*3
        assert sum(prices.values())==67 and len(posts)==32 and set(posts.values())=={1}
        assert await pool.fetchval("SELECT price->>'total' FROM task_price_quotes WHERE id=$1",pending)=='150'
        print('after three explicit confirmations: 67 price GET, 32 generation POST',flush=True)


RESTART = r"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import os
from uuid import UUID
import asyncpg,httpx
from elevenbot.config import Config
from elevenbot.task_launch import recover_interrupted
from test_provider_extensibility import app_with_fixture
from test_ui import Bot

async def run():
 pool=await asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],
        server_settings={'search_path':os.environ['RESTART_SCHEMA']})
 q=UUID(os.environ['RESTART_QUOTE'])
 if os.environ['RESTART_PHASE']=='recover':
    await recover_interrupted(pool)
    print(await pool.fetchval('SELECT state FROM task_dispatch WHERE quote_id=$1',q),flush=True)
    await pool.close()
    return
 def respond(req):
    print(req.method+' '+req.url.path,flush=True)
    assert req.method=='GET' and req.url.path=='/price'
    return httpx.Response(200,json={'amount':100})
 async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(respond)) as client:
    app=app_with_fixture(pool,Config(),Bot(),client)
    if os.environ['RESTART_BOUNDARY']=='dispatching':
        async def stop_before_post(*args):
            os._exit(71)
        app.providers.launches['fixture'].run=stop_before_post
    @asynccontextmanager
    async def progress(request):
        if os.environ['RESTART_BOUNDARY']=='pending':
            os._exit(71)
        yield
    await app.launch.confirm(UUID(os.environ['RESTART_USER']),100,q,7,progress=progress,background=None)
asyncio.run(run())
"""


@pytest.mark.parametrize('boundary,terminal,notice',[
    ('pending','interrupted','до отправки'),('dispatching','uncertain','исход запуска'),
])
async def test_process_restart_after_acceptance_before_post(env,boundary,terminal,notice):
    pool,cfg,_,user=env
    bot=Bot()
    counts=Counter()

    def respond(req):
        counts[req.method]+=1
        assert req.method=='GET'
        return httpx.Response(200,json={'amount':100})

    async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(respond)) as http:
        app=app_with_fixture(pool,cfg,bot,http)
        q=await app.pricing.quote(user,Request('fixture','fixture/restart','chat','Restart model','Prompt'))
        schema=await pool.fetchval('SELECT current_schema()')
        root=Path(__file__).resolve().parents[1]
        async def process(phase):
            env_vars=os.environ|{'RESTART_SCHEMA':schema,'RESTART_QUOTE':str(q.id),
                'RESTART_USER':str(user),'RESTART_PHASE':phase,'RESTART_BOUNDARY':boundary,
                'PYTHONPATH':os.pathsep.join((str(root/'src'),str(root/'tests')))}
            proc=await asyncio.create_subprocess_exec(sys.executable,'-c',RESTART,env=env_vars,
                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            stdout,stderr=await asyncio.wait_for(proc.communicate(),15)
            return proc.returncode,stdout.decode(),stderr.decode()

        code,output,stderr=await process('accept')
        assert code==71 and output.strip()=='GET /price',stderr
        row=await pool.fetchrow("""
            SELECT q.state AS quote_state,q.price->>'total' AS total,d.state AS dispatch
            FROM task_price_quotes q JOIN task_dispatch d ON d.quote_id=q.id WHERE q.id=$1
            """,q.id)
        assert tuple(row)==('accepted','100',boundary)
        code,output,stderr=await process('recover')
        assert code==0 and output.strip()==terminal,stderr
        await notify_interrupted(pool,bot)
        assert notice in bot.sent[-1][0].lower()
        count=len(bot.sent)
        await notify_interrupted(pool,bot)
        assert len(bot.sent)==count
        with pytest.raises(Rejected):
            await app.confirm_price(user,100,q.id,8)
        assert counts=={'GET':1} and await pool.fetchval('SELECT count(*) FROM interaction_attempts')==1
        assert not await pool.fetchval('SELECT count(*) FROM task_chat_works')
        print(f'restart {boundary}: 2 price GET, 0 generation POST, accepted price 100, state {terminal}',flush=True)
