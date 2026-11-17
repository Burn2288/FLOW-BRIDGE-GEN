import asyncio
from base64 import b64encode
from dataclasses import replace
from decimal import Decimal
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from elevenbot.anymodel import AnyModelProvider,FIBO_MODEL,IMAGE_OP,TEST_MODEL
from elevenbot.anymodel_speech import FISH,SpeechPilot
from elevenbot.anymodel_video import MODEL,AnyModelVideoPilot,AnyModelVideoProvider
from elevenbot.pricing import ProviderCost,Request
from elevenbot.tariff_admin import default_params
from elevenbot.task_launch import TaskLaunch
from elevenbot.telegram import TelegramApp
from test_admin_access import event
from test_anymodel import routes
from test_anymodel_speech import MP3
from test_image_validation import encoded_image
from test_ui import Bot
from test_video import video

MODELS={'chat':TEST_MODEL,IMAGE_OP:FIBO_MODEL,'video':MODEL,'audio.speech':FISH}


@pytest.fixture
def admin_already_signed_in():
    pass


class Price:
    async def cost(self,request):
        return ProviderCost(Decimal(60),'darkflow_token',False,'fixture','1 операция')


class Transport(Bot):
    def __init__(self,fail_delivery):
        super().__init__()
        self.fail_delivery=fail_delivery
        self.delivery_attempts=0
        self.send_photo=AsyncMock(side_effect=self.media)
        self.send_video=AsyncMock(side_effect=self.media)
        self.send_audio=AsyncMock(side_effect=self.media)

    def failure(self):
        return TelegramNetworkError(SendMessage(chat_id=100,text='fixture'),'fixture delivery failure')

    async def media(self,*args,**kwargs):
        self.delivery_attempts+=1
        if self.fail_delivery:
            raise self.failure()
        return SimpleNamespace(message_id=50)

    async def send_message(self,chat,text,reply_markup=None):
        if text=='fixture answer':
            self.delivery_attempts+=1
            if self.fail_delivery:
                raise self.failure()
        return await super().send_message(chat,text,reply_markup)


@pytest.mark.parametrize(('operation','variant'),[
    *((op,variant) for op in MODELS for variant in ('success','refusal','delivery_error','unknown')),
    ('chat','billable_400'),
    ('chat','unclassified_400'),
])
async def test_lifecycle(env,confirmed_credit,operation,variant,video,monkeypatch):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True,anymodel_key='fixture',
                anymodel_chat_live=True,anymodel_image_live=True,anymodel_video_live=True,anymodel_speech_live=True,
                interaction_limit=10)
    await confirmed_credit(pool,cfg,user,100)
    model=MODELS[operation]
    png=encoded_image('PNG')
    bot=Transport(variant=='delivery_error')
    posts=[]
    async def respond(req):
        path=req.url.path
        if req.method=='POST':
            posts.append(path)
            assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='task_reserve'")==1
            assert await pool.fetchval("SELECT reserved FROM wallets WHERE mode='live' AND user_id=$1",user)==60
            assert await pool.fetchval("SELECT count(*) FROM task_price_quotes WHERE state='accepted'")==1
            if variant=='unknown':
                raise httpx.ReadTimeout('fixture unknown')
            if variant in ('refusal','billable_400','unclassified_400'):
                codes={'refusal':'bad_request','billable_400':'output_budget_exhausted',
                       'unclassified_400':'unrecognized_error'}
                return httpx.Response(400,json={'error':{'code':codes[variant],'type':'invalid_request_error'}})
            if operation=='chat':
                return httpx.Response(200,json={'choices':[{'message':{'content':'fixture answer'}}]})
            if operation==IMAGE_OP:
                return httpx.Response(200,json={'data':[{'b64_json':b64encode(png).decode()}]})
            if operation=='audio.speech':
                return httpx.Response(200,content=MP3,headers={'Content-Type':'audio/mpeg'})
            return httpx.Response(202,json={'request_id':'fixture-video'},headers={'x-9router-connection-id':'fixture'})
        if path=='/v1/videos/fixture-video':
            return httpx.Response(200,json={'status':'done','video':{'url':'fixture'}})
        assert path=='/v1/videos/fixture-video/content',path
        return httpx.Response(200,content=video,headers={'Content-Type':'video/mp4'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        api=AnyModelProvider(cfg.anymodel_key,client=http)
        monkeypatch.setattr('elevenbot.telegram.AnyModelProvider',lambda key:api)
        def app_for(transport):
            app=TelegramApp(pool,cfg,transport)
            app.anymodel_images.adapter=api
            app.anymodel_speech=SpeechPilot(pool,cfg,api=api)
            app.anymodel_video=AnyModelVideoPilot(pool,cfg,api=AnyModelVideoProvider(cfg.anymodel_key,client=http))
            app.pricing.adapters['anymodel']=Price()
            return app
        app=app_for(bot)
        req=Request('anymodel',model,operation,'Fixture','fixture prompt',default_params('anymodel',operation))
        quote=await app.pricing.quote(user,req)
        assert not posts
        confirm=f'amconfirm:{quote.id}'
        try:
            await app.handle(event(10,callback=confirm))
        except TelegramNetworkError:
            assert variant=='delivery_error'
        if operation=='video' and variant in ('success','delivery_error'):
            assert await app.anymodel_video.poll_one(bot)
        if operation==IMAGE_OP and variant in ('success','delivery_error'):
            assert await app.anymodel_images.poll_one(bot)
        before_restart=await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",user)
        script = '''
import asyncio, os, asyncpg
from elevenbot.task_launch import recover_interrupted
async def main():
    async with asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],min_size=1,max_size=1,
            server_settings={'search_path':os.environ['REFUSAL_SCHEMA']}) as pool:
        await recover_interrupted(pool)
        await recover_interrupted(pool)
asyncio.run(main())
'''
        source=Path(__file__).resolve().parents[1]/'src'
        process=await asyncio.create_subprocess_exec(sys.executable,'-c',script,
            env=os.environ|{'REFUSAL_SCHEMA':await pool.fetchval('SELECT current_schema()'),'PYTHONPATH':str(source)},
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        _,stderr=await asyncio.wait_for(process.communicate(),10)
        assert process.returncode==0,stderr.decode()
        restarted_bot=Transport(False)
        restarted=app_for(restarted_bot)
        await restarted.handle(event(11,callback=confirm))
        state=await pool.fetchval('SELECT state FROM task_dispatch WHERE quote_id=$1',quote.id)
        wallet=await restarted.svc.wallet(user)
        balance=(wallet['available'],wallet['reserved'])
        ledger=await pool.fetch("SELECT kind,da,dr FROM ledger WHERE task_quote_id=$1 ORDER BY created_at,kind DESC",quote.id)
        movements={r['kind']:(r['da'],r['dr']) for r in ledger}
        assert len(posts)==1
        assert await restarted.svc.reconcile()==0
        if variant in ('success','delivery_error'):
            assert balance==(40,0) and movements=={'task_reserve':(-60,60),'task_capture':(0,-60)}
            assert bot.delivery_attempts==1
            if variant=='delivery_error':
                await restarted.handle(event(12,callback='history:0'))
                await restarted.handle(event(13,callback=routes(restarted_bot)['Открыть работу №1']))
                assert restarted_bot.delivery_attempts==1
            result='capture'
        elif variant=='refusal':
            assert balance==(100,0) and movements=={'task_reserve':(-60,60),'task_release':(60,-60)}
            assert state==('uncertain' if operation==IMAGE_OP else 'rejected')
            result='release'
        else:
            assert balance==(40,60) and movements=={'task_reserve':(-60,60)}
            assert state=='uncertain'
            result='unknown; held after restart'
        if variant not in ('success','delivery_error') or operation!='video':
            assert tuple(before_restart)==balance
        print(f'RELEASE_RESULT|{operation}|{variant}|100|{balance[0]}|{balance[1]}|{len(posts)}|{result}',flush=True)


async def test_funded_ordinary_user_launches_only_with_isolated_adapter_policy(env,confirmed_credit):
    from test_provider_extensibility import app_with_fixture
    pool,cfg,_,admin=env
    calls=[]
    async def respond(req):
        calls.append(req.method)
        if req.method=='GET':
            return httpx.Response(200,json={'amount':60})
        assert req.method=='POST' and req.url.path=='/generate'
        assert await pool.fetchval("SELECT reserved FROM wallets WHERE user_id=$1 AND mode='live'",user)==60
        return httpx.Response(200,json={'answer':'fixture answer'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond),base_url='https://fixture.invalid') as http:
        bot=Bot()
        app=app_with_fixture(pool,cfg,bot,http)
        user=await app.svc.identity(101)
        await app.svc.accept(user)
        await confirmed_credit(pool,cfg,user,100)
        await app.pricing.set_rate(admin,100,'fixture_token','1',provider='fixture')
        await pool.execute("INSERT INTO approved_models VALUES('fixture','fixture/pilot','chat','Fixture')")
        quote=await app.pricing.quote(user,Request('fixture','fixture/pilot','chat','Fixture','Prompt'))
        await app.handle(event(1,chat=101,callback=f'amconfirm:{quote.id}'))
        assert bot.sent[-1][0]=='Тестовый запуск для этого аккаунта недоступен.'
        assert calls==['GET','GET']
        assert not await pool.fetchval('SELECT count(*) FROM task_dispatch')
        assert not await pool.fetchval('SELECT count(*) FROM ledger WHERE task_quote_id IS NOT NULL')
        wallet=await app.svc.wallet(user)
        assert (wallet['available'],wallet['reserved'])==(100,0)
        async def authorize_stub(conn,task_user,external):
            assert external not in app.cfg.admin_ids and task_user==user
            assert await conn.fetchval(
                "SELECT 1 FROM identities WHERE platform='telegram' AND external_id=$1 AND user_id=$2",
                external,task_user,
            )

        app.launch=TaskLaunch(app.pricing,{'fixture':app.providers.launches['fixture']},authorize=authorize_stub)
        await app.handle(event(2,chat=101,callback=f'amconfirm:{quote.id}'))
        await app.handle(event(3,chat=101,callback=f'amconfirm:{quote.id}'))
        assert calls.count('POST')==1
        assert any(text=='fixture answer' for text,_ in bot.sent)
        wallet=await app.svc.wallet(user)
        assert (wallet['available'],wallet['reserved'])==(40,0)
        assert [tuple(r) for r in await pool.fetch(
            "SELECT kind,da,dr FROM ledger WHERE task_quote_id=$1 ORDER BY kind",quote.id,
        )]==[('task_capture',0,-60),('task_reserve',-60,60)]
        print('RELEASE_RESULT|ordinary|fixture|100|40|0|1|isolated adapter, default live policy unchanged',flush=True)


@pytest.mark.parametrize('operation',['chat','audio.speech','video'])
async def test_clodex_structured_rejection(operation):
    from elevenbot.config import Config
    from elevenbot.interaction import execute
    from elevenbot.providers import ClodexProvider,DefinitiveFailure
    from elevenbot.submission import ProviderRefused
    from elevenbot.video import MODES,VideoAPI

    async def respond(req):
        assert req.method=='POST'
        return httpx.Response(400,json={'error':{'type':'invalid_request_error','code':'bad_request'}})

    transport=httpx.MockTransport(respond)
    async with httpx.AsyncClient(transport=transport) as client:
        if operation=='chat':
            model={'id':'fixture/chat','provider':'clodex','availability':'key_available','protocols':['openai']}
            with pytest.raises(ProviderRefused):
                await execute('chat',model,'fixture',[],mode='live',key='fixture',client=client)
        elif operation=='audio.speech':
            with pytest.raises(DefinitiveFailure):
                await ClodexProvider(Config(clodex_key='fixture',clodex_model='fixture/speech'),client).synthesize('fixture','voice',1)
        else:
            with pytest.raises(ProviderRefused):
                await VideoAPI('fixture',transport=transport).create(MODES['standard'][0],'fixture')
