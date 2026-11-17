import asyncio,uuid
from types import SimpleNamespace
import pytest
from elevenbot.demo import DemoService,DemoApp,Pairing,deliver
from elevenbot.core import Rejected
from elevenbot.config import Config
from elevenbot.telegram import MENU
from test_ui import Bot,event

async def test_demo_real_ui_vertical_slice():
    bot=Bot();svc=DemoService();app=DemoApp(Config(mode='mock',generation_enabled=True),bot,svc)
    for update in [event('/start'),event(callback='accept'),event("🎙 Создать озвучку"),event('Hello'),event(callback='voice:0'),event(callback='speed:1.0')]:await app.handle(update)
    cb=bot.sent[-1][1].inline_keyboard[0][0].callback_data
    await app.handle(event(callback=cb));j=next(iter(svc.jobs))
    worker=asyncio.create_task(deliver(svc))
    try:await asyncio.wait_for(svc.requests.join(),2)
    finally:worker.cancel();await asyncio.gather(worker,return_exceptions=True)
    await app.refresh_speech_results()
    assert svc.jobs[j]['status']=='succeeded' and len(bot.audio)==1
    assert 'ТЕСТ' in bot.audio[0][1]['caption']
    assert 'Clodex и оплата выключены' in bot.audio[0][1]['caption']

async def test_demo_confirm_x20_and_ownership():
    s=DemoService();u=await s.identity(100);await s.accept(u);q,_=await s.quote(u,'test','demo')
    jobs=await asyncio.gather(*(s.confirm(u,q) for _ in range(20)))
    assert len(set(jobs))==1 and s.requests.qsize()==1
    v=await s.identity(101);await s.accept(v)
    with pytest.raises(Rejected):await s.owned(v,jobs[0])
    with pytest.raises(Rejected):await s.confirm(v,q)

async def test_demo_no_financial_entrypoints():
    s=DemoService()
    assert not await s.precheckout()
    with pytest.raises(Rejected):await s.order()
    bot=Bot();app=DemoApp(Config(),bot,s)
    payment={'currency':'XTR','total_amount':100,'invoice_payload':str(uuid.uuid4()),'telegram_payment_charge_id':'fixture','provider_payment_charge_id':''}
    await app.handle(event(payment=payment))
    assert 'не выполняются' in bot.sent[-1][0]
    assert not s.jobs and not s.users

def test_pairing_is_private_one_time_owner_binding():
    p=Pairing();code=p.code
    assert not p.allow(100,'/start wrong')
    assert not p.allow(100,'/start ')
    assert not p.allow(100,'/start неверный')
    assert p.allow(100,'/start '+code)
    assert p.allow(100,'hello') and not p.allow(101,'/start '+code)
    assert not p.code

async def test_demo_state_resets():
    s=DemoService();u=await s.identity(100);await s.accept(u)
    assert (await s.wallet(u))['available']==10000
    new=DemoService();assert not new.users and not new.jobs

async def test_demo_real_sdk_local_http_audio():
    from aiohttp import web
    from aiogram import Bot as RealBot
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.client.telegram import TelegramAPIServer
    calls=[]
    async def endpoint(request):
        method=request.match_info['method'];form=await request.post();calls.append(method)
        if method=='sendAudio':
            attachment = form['audio']
            assert attachment.startswith('attach://')
            content = form[attachment.removeprefix('attach://')].file.read()
            assert len(content)>128
        if method in ('answerCallbackQuery','deleteMessage'):
            return web.json_response({'ok':True,'result':True})
        return web.json_response({'ok':True,'result':{'message_id':len(calls),'date':1,'chat':{'id':100,'type':'private'}}})
    app=web.Application();app.router.add_post('/bot{token}/{method}',endpoint)
    runner=web.AppRunner(app,access_log=None);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    session=AiohttpSession(api=TelegramAPIServer.from_base(f'http://127.0.0.1:{port}'))
    try:
        async with RealBot(str(123456)+':'+('fixture_'*5),session=session) as bot:
            svc=DemoService();ui=DemoApp(Config(),bot,svc)
            for update in [event('/start'),event(callback='accept'),event("🎙 Создать озвучку"),event('Hello'),event(callback='voice:0'),event(callback='speed:1.0')]:await ui.handle(update)
            q=next(iter(svc.quotes));await ui.handle(event(callback='confirm:'+str(q)))
            worker=asyncio.create_task(deliver(svc))
            try:await asyncio.wait_for(svc.requests.join(),3)
            finally:worker.cancel();await asyncio.gather(worker,return_exceptions=True)
            await ui.refresh_speech_results()
            assert calls.count('sendAudio')==1
    finally:await runner.cleanup()
