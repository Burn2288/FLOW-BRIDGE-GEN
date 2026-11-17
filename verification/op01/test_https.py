"""Ephemeral localhost-only Caddy/Unix-socket/Mini App/PostgreSQL exercise."""
import asyncio
import os
import socket
import ssl
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import aiohttp
import asyncpg
import pytest
from aiohttp import web

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))

from elevenbot.config import Config
from elevenbot.db import migrate
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed
from test_ui import Bot, event

FIXTURE_TOKEN = 'op01-test-token-not-a-real-telegram-token'


def safe_dsn(raw, marker):
    u=urlsplit(raw)
    if not (marker=='YES' and u.scheme=='postgresql' and u.hostname=='127.0.0.1'
            and u.port==55432 and u.path=='/op01_test' and u.username=='postgres'
            and not u.query and not u.fragment):
        raise ValueError('OP01 requires its explicitly disposable local PostgreSQL service')
    return raw


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]


def test_dsn_guard_fails_before_connect():
    for value in ('postgresql://postgres:x@production.example:55432/op01_test',
                  'postgresql://postgres:x@127.0.0.1:5432/op01_test',
                  'postgresql://postgres:x@127.0.0.1:55432/other'):
        with pytest.raises(ValueError):safe_dsn(value,'YES')
    with pytest.raises(ValueError):safe_dsn('postgresql://postgres:x@127.0.0.1:55432/op01_test','NO')


@pytest.mark.skipif(os.name=='nt',reason='Unix socket and test Caddy profile require Linux')
async def test_https_proxy_security_and_shared_postgres(tmp_path, caplog):
    dsn=safe_dsn(os.environ.get('OP01_TEST_DATABASE_URL',''),os.environ.get('OP01_DISPOSABLE_POSTGRES',''))
    schema='op01_'+uuid4().hex
    admin=await asyncpg.connect(dsn)
    pool=runner=proxy=None
    sock=tmp_path/'backend.sock'
    cert=tmp_path/'fixture-cert.pem';key=tmp_path/'fixture-key.pem';proxy_log=tmp_path/'caddy.log'
    http_port,tls_port=port(),port()
    assert http_port!=tls_port
    try:
        await admin.execute('CREATE SCHEMA '+schema)
        pool=await asyncpg.create_pool(dsn,min_size=1,max_size=4,server_settings={'search_path':schema})
        await migrate(pool)
        cfg=Config(token=FIXTURE_TOKEN,mode='mock',access_mode='private',admin_ids=(100,),pilot_user_ids=(101,),
                   payments_enabled=False,generation_enabled=False,storage=tmp_path/'storage')
        telegram=TelegramApp(pool,cfg,Bot())
        await telegram.handle(event('/start'))
        await telegram.handle(event(callback='accept'))
        owner=await telegram.svc.identity(100)
        tester=await telegram.svc.identity(101);await telegram.svc.accept(tester)
        assert await pool.fetchval("SELECT count(*) FROM identities WHERE platform='telegram' AND external_id=100")==1
        assert await pool.fetchval('SELECT count(*) FROM wallets WHERE user_id=$1',owner)==2
        assert not telegram.has_admin_session(101)

        async def start_backend(config):
            app=create_app(pool,config)
            async def observed(request):
                return web.json_response({k:request.headers.get(k,'') for k in
                    ('Host','Forwarded','X-Forwarded-For','X-Forwarded-Proto','X-Forwarded-Host')})
            async def crash(request):
                raise RuntimeError('fixture-exception-marker')
            app.router.add_get('/api/v1/_op01-observed',observed)
            app.router.add_get('/api/v1/_op01-error',crash)
            r=web.AppRunner(app,access_log=None);await r.setup()
            site=web.UnixSite(r,str(sock));await site.start()
            assert site._server.sockets[0].family==socket.AF_UNIX
            os.chmod(sock,0o600)
            return r

        runner=await start_backend(cfg)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                        '-keyout',str(key),'-out',str(cert),'-subj','/CN=localhost',
                        '-addext','subjectAltName=DNS:localhost'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        template=(ROOT/'deploy/test/op01/Caddyfile.template').read_text(encoding='utf-8')
        for name,value in {'__HTTP_PORT__':str(http_port),'__HTTPS_PORT__':str(tls_port),
                           '__CERT_PATH__':str(cert),'__KEY_PATH__':str(key),'__SOCKET_PATH__':str(sock)}.items():
            template=template.replace(name,value)
        conf=tmp_path/'Caddyfile';conf.write_text(template,encoding='utf-8')
        subprocess.run(['caddy','validate','--config',str(conf),'--adapter','caddyfile'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        with proxy_log.open('wb') as output:
            proxy=await asyncio.create_subprocess_exec('caddy','run','--config',str(conf),'--adapter','caddyfile',stdout=output,stderr=output)
        tls=ssl.create_default_context(cafile=str(cert))
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=tls,force_close=True)) as client:
            base=f'https://localhost:{tls_port}'
            for _ in range(100):
                if proxy.returncode is not None:raise RuntimeError('test Caddy exited before readiness')
                try:
                    response=await client.get(base+'/healthz');break
                except aiohttp.ClientConnectorError:
                    await asyncio.sleep(.1)
            else:raise RuntimeError('test Caddy did not become ready')
            assert response.status==200 and await response.json()=={'status':'ok'}
            assert response.headers.get('Set-Cookie') is None
            print('HTTPS_HEALTH=200; backend=unix-socket; tls=fixture-ca-verified')
            async with aiohttp.ClientSession() as untrusted:
                with pytest.raises(aiohttp.ClientConnectorCertificateError):await untrusted.get(base+'/healthz')
            response=await client.get(f'http://localhost:{http_port}/healthz',allow_redirects=False)
            assert response.status==308 and response.headers['Location']==base+'/healthz'
            assert (await client.get(base+'/healthz',headers={'Host':'attacker.invalid'})).status in (400,404,421)
            assert (await client.get(base+'/_private')).status==404
            response=await client.get(base+'/api/v1/_op01-observed',headers={'Forwarded':'for=8.8.8.8;proto=http',
                'X-Forwarded-For':'8.8.8.8','X-Forwarded-Proto':'http','X-Forwarded-Host':'attacker.invalid'})
            observed=await response.json()
            assert observed=={'Host':'localhost','Forwarded':'','X-Forwarded-For':'127.0.0.1',
                              'X-Forwarded-Proto':'https','X-Forwarded-Host':'localhost'}
            print('PROXY_HEADERS=rewritten; external-listeners=loopback; nonallowlisted=404; http=308')
            response=await client.get(base+'/api/v1/wallet',headers={'Origin':'https://attacker.invalid',
                'X-Forwarded-For':'127.0.0.1','X-Forwarded-Proto':'https'})
            assert response.status==401 and 'Access-Control-Allow-Origin' not in response.headers
            assert response.headers.get('Set-Cookie') is None
            assert (await client.post(base+'/api/v1/session',json={'initData':signed('incorrect',100)})).status==401
            assert (await client.post(base+'/api/v1/session',json={'initData':signed(FIXTURE_TOKEN,100,age=360)})).status==401
            assert (await client.post(base+'/api/v1/session',json={'initData':signed(FIXTURE_TOKEN,102)})).status==403
            assert not await pool.fetchval("SELECT EXISTS(SELECT 1 FROM identities WHERE external_id=102)")
            response=await client.post(base+'/api/v1/session',json={'initData':signed(FIXTURE_TOKEN,100)})
            assert response.status==200 and response.headers.get('Set-Cookie') is None
            owner_token=(await response.json())['token']
            response=await client.post(base+'/api/v1/session',json={'initData':signed(FIXTURE_TOKEN,101)})
            assert response.status==200
            tester_token=(await response.json())['token']
            headers={'Authorization':'Bearer '+owner_token}
            assert (await client.get(base+'/api/v1/wallet',headers=headers)).status==200
            assert (await client.get(base+'/api/v1/admin',headers={'Authorization':'Bearer '+tester_token})).status==404
            work=await telegram.svc.save_image_work(owner,9001,'fixture','fixture',
                        type('Image',(),{'image':b'fixture-image','filename':'test.png'})())
            foreign=await client.get(base+'/api/v1/works/image/'+str(work),headers={'Authorization':'Bearer '+tester_token})
            assert foreign.status==404
            assert (await client.post(base+'/api/v1/session',data='x'*13000,headers={'Content-Type':'application/json'})).status==413
            crash=await client.get(base+'/api/v1/_op01-error');crash_body=await crash.text()
            assert crash.status==500 and 'Traceback' not in crash_body and 'fixture-exception-marker' not in crash_body
            assert FIXTURE_TOKEN not in crash_body and owner_token not in crash_body and tester_token not in crash_body
            assert await telegram.svc.identity(100)==owner
            assert await pool.fetchval('SELECT count(*) FROM wallets WHERE user_id=$1',owner)==2
            print('HTTPS_AUTH=pass; outsider=403; tester_admin=denied; foreign_work=404; body_limit=413; no-cors/no-cookie')
            await runner.cleanup();runner=None
            sock.unlink(missing_ok=True)
            runner=await start_backend(replace(cfg,pilot_user_ids=()))
            assert (await client.get(base+'/api/v1/wallet',headers={'Authorization':'Bearer '+tester_token})).status==403
            assert (await client.post(base+'/api/v1/session',json={'initData':signed(FIXTURE_TOKEN,101,age=1)})).status==403
            assert await pool.fetchval('SELECT count(*) FROM wallets WHERE user_id=$1',tester)==2
            print('REVOKE_AFTER_BACKEND_RESTART=pass; existing_wallets=preserved')
        proxy.terminate();await asyncio.wait_for(proxy.wait(),10)
        assert proxy.returncode is not None
        async with aiohttp.ClientSession() as stopped:
            with pytest.raises(aiohttp.ClientConnectorError):await stopped.get(f'http://127.0.0.1:{http_port}/')
        log=proxy_log.read_text(encoding='utf-8',errors='replace')
        assert FIXTURE_TOKEN not in log and owner_token not in log and tester_token not in log
        assert FIXTURE_TOKEN not in caplog.text and owner_token not in caplog.text and tester_token not in caplog.text
        print('SHUTDOWN=pass; fixture-tokens-absent-from-logs=true')
    finally:
        if proxy and proxy.returncode is None:
            proxy.terminate()
            try:await asyncio.wait_for(proxy.wait(),10)
            except TimeoutError:proxy.kill();await proxy.wait()
        if runner:await runner.cleanup()
        if pool:await pool.close()
        await admin.execute('DROP SCHEMA IF EXISTS '+schema+' CASCADE')
        await admin.close()
