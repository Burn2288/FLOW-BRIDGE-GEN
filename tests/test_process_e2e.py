"""Real bot + worker subprocesses, PostgreSQL, MOCK tone and local Telegram HTTP stub.
This is engineering E2E, never Telegram LIVE or real ElevenLabs speech evidence.
"""
import os,sys,asyncio,json,time,uuid
import pytest
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from aiohttp import web
from elevenbot.telegram import MENU

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('runtime_role',[False,True])
async def test_bot_worker_process_mock_e2e(env,runtime_role):
    pool,cfg,s,u=env
    await pool.execute('UPDATE identities SET accepted_at=NULL,terms_version=NULL WHERE user_id=$1',u)
    schema=await pool.fetchval('SELECT current_schema()')
    parts=urlsplit(os.environ['TEST_DATABASE_URL'])
    role=None
    if runtime_role:
        role='process_runtime_'+uuid.uuid4().hex
        secret='isolated-test-only'
        await pool.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{secret}' NOSUPERUSER NOCREATEDB NOCREATEROLE")
        await pool.execute(f'GRANT USAGE ON SCHEMA {schema} TO {role}')
        await pool.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}')
        await pool.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {role}')
        host=('['+parts.hostname+']') if ':' in parts.hostname else parts.hostname
        parts=parts._replace(netloc=f'{role}:{secret}@{host}:{parts.port or 5432}')
    dsn=urlunsplit(parts._replace(query=urlencode(parse_qsl(parts.query)+[('search_path',schema)])))
    received=[];stage=0
    async def api(request):
        nonlocal stage
        method=request.match_info['method'].lower();form=await request.post()
        if method=='getupdates':
            if stage>=7:
                await asyncio.sleep(.05);return web.json_response({'ok':True,'result':[]})
            texts=['/start',None,'🎙 Создать озвучку','Hello integrated',None,None,None]
            callbacks={1:'accept',4:'voice:0',5:'speed:1.0'}
            if stage==6:
                quote=await pool.fetchval('SELECT id FROM quotes ORDER BY created_at DESC LIMIT 1')
                if quote is None:return web.json_response({'ok':True,'result':[]})
                callbacks[6]='confirm:'+str(quote)
            msg={'message_id':stage+1,'date':int(time.time()),'chat':{'id':100,'type':'private'},'from':{'id':100,'is_bot':False,'first_name':'Fixture'}}
            update={'update_id':stage+1}
            if stage in callbacks:update['callback_query']={'id':'callback'+str(stage),'from':msg['from'],'chat_instance':'fixture','message':msg,'data':callbacks[stage]}
            else:msg['text']=texts[stage];update['message']=msg
            stage+=1
            return web.json_response({'ok':True,'result':[update]})
        if method in ('answercallbackquery','deletemessage'):
            return web.json_response({'ok':True,'result':True})
        if method in ('sendmessage','editmessagetext','editmessagecaption','sendanimation','sendaudio','sendphoto'):
            received.append(method)
            message_id = int(form['message_id']) if method in ('editmessagetext','editmessagecaption') else len(received) + 100
            return web.json_response({'ok':True,'result':{'message_id':message_id,'date':int(time.time()),'chat':{'id':100,'type':'private'}}})
        return web.json_response({'ok':False,'error_code':400,'description':'Unhandled fixture method'},status=400)
    app=web.Application(client_max_size=3*1024**2);app.router.add_post('/bot{token}/{method}',api)
    runner=web.AppRunner(app,access_log=None);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    config=os.environ|{'DATABASE_URL':dsn,'PROVIDER_MODE':'mock','GENERATION_ENABLED':'true','PAYMENTS_ENABLED':'false',
        'TELEGRAM_BOT_TOKEN':str(123456)+':'+('fixture_'*5),'TELEGRAM_API_BASE':f'http://127.0.0.1:{port}',
        'ALLOW_LOCAL_TELEGRAM_STUB':'true','AUDIO_STORAGE_DIR':str(cfg.storage),'PYTHONUNBUFFERED':'1',
        'PYTHONPATH':str(ROOT/'src')}
    processes=[]
    try:
        for name in ('bot','worker'):
            processes.append(await asyncio.create_subprocess_exec(sys.executable,'-m','elevenbot',name,env=config,
                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert all(p.returncode is None for p in processes),'Executable process stopped; inspect sanitized process logs'
            row=await pool.fetchrow('SELECT j.status,j.settlement,d.status delivery,f.storage_key FROM jobs j JOIN files f ON f.job_id=j.id JOIN deliveries d ON d.job_id=j.id')
            if row and 'sendaudio' in received:break
            await asyncio.sleep(.1)
        else:raise AssertionError('Integrated MOCK E2E did not finish in 30 seconds')
        assert row['status']=='succeeded' and row['settlement']=='capture'
        # The active gateway sends directly. Durable delivery acknowledgement is
        # a separate gap in this baseline, even when the HTTP stub receives audio.
        assert row['delivery']=='pending'
        assert Path(cfg.storage/row['storage_key']).is_file()
        assert received.count('sendaudio')==1
        assert received.count('sendphoto')==1
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='capture'")==1
        assert (await s.wallet(u))['reserved']==0
        # Restart actual executable processes against the same persisted database.
        for p in processes:p.terminate()
        for p in processes:await asyncio.wait_for(p.communicate(),5)
        processes.clear()
        restart_at=await pool.fetchval('SELECT now()')
        for name in ('bot','worker'):
            processes.append(await asyncio.create_subprocess_exec(sys.executable,'-m','elevenbot',name,env=config,
                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE))
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            assert all(p.returncode is None for p in processes)
            ready=await pool.fetchval('SELECT count(*) FROM heartbeat WHERE seen_at>$1',restart_at)
            if ready==2:break
            await asyncio.sleep(.1)
        else:raise AssertionError('Persisted processes failed to resume')
        assert await pool.fetchval('SELECT count(*) FROM jobs')==1
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='capture'")==1
        assert await pool.fetchval('SELECT offset_id FROM poll_state WHERE id=1')>=8
        assert received.count('sendaudio')==1

    finally:
        for p in processes:
            if p.returncode is None:p.terminate()
        for p in processes:
            try:await asyncio.wait_for(p.communicate(),5)
            except asyncio.TimeoutError:p.kill();await p.communicate()
        await runner.cleanup()
        if role:
            await pool.execute(f'DROP OWNED BY {role}')
            await pool.execute(f'DROP ROLE {role}')
