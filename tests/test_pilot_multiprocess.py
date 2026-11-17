"""Three actual subprocesses; all share a disposable PostgreSQL schema."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import aiohttp
import pytest

from elevenbot.interaction import MOCK_IMAGE
from miniapp.backend.web import token_hash
from miniapp.tests.test_miniapp import signed

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('users', 'identities', 'wallets', 'ledger', 'quotes', 'jobs', 'payments', 'task_price_quotes', 'task_dispatch')


async def counts(pool):
    return {name: await pool.fetchval('SELECT count(*) FROM ' + name) for name in TABLES}


async def start_process(schema, kind, allow):
    child_env = os.environ.copy()
    child_env.update({'ACCESS_MODE': 'private', 'ADMIN_TELEGRAM_IDS': '100',
                      'PILOT_TELEGRAM_USER_IDS': '101' if allow else '',
                      'PROVIDER_MODE': 'mock', 'GENERATION_ENABLED': 'false',
                      'PAYMENTS_ENABLED': 'false', 'TELEGRAM_BOT_TOKEN': 'fixture',
                      'PILOT_FIXTURE_SCHEMA': schema, 'PILOT_FIXTURE_KIND': kind,
                      'PYTHONPATH': str(ROOT / 'src') + os.pathsep + str(ROOT),
                      'PYTHONUNBUFFERED': '1'})
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / 'verification' / 'pilot_process.py'), cwd=ROOT,
        env=child_env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        line = await asyncio.wait_for(process.stdout.readline(), 30)
        port = json.loads(line)['port']
    except Exception:
        if process.returncode is None:
            process.terminate()
        await process.wait()
        raise AssertionError('fixture process did not start; output withheld') from None
    return process, f'http://127.0.0.1:{port}'


async def stop_process(process):
    if process.returncode is None:
        process.terminate()
    await asyncio.wait_for(process.wait(), 10)


async def request(client, url, *, body=None, headers=None):
    async with (client.post(url, json=body, headers=headers) if body is not None else
                client.get(url, headers=headers)) as response:
        try:
            payload = await response.json()
        except (aiohttp.ContentTypeError, json.JSONDecodeError):
            payload = None
        return response.status, payload


async def test_private_admission_across_three_processes(env):
    pool, _, service, admin = env
    schema = await pool.fetchval('SELECT current_schema()')
    admin_work = await service.save_image_work(admin, -901, 'fixture/image', 'fixture',
        SimpleNamespace(image=MOCK_IMAGE, filename='fixture.png'))
    processes = []
    async def launch(kind, allow):
        process, url = await start_process(schema, kind, allow)
        processes.append(process)
        return process, url
    try:
        a, url_a = await launch('telegram', True)
        b, url_b = await launch('telegram', True)
        mini, url_m = await launch('miniapp', True)
        async with aiohttp.ClientSession() as client:
            metas = [(await request(client, u + '/fixture/metadata'))[1] for u in (url_a, url_b, url_m)]
            assert len({m['pid'] for m in metas}) == 3
            assert len({m['backend'] for m in metas}) == 3
            assert len({(m['db'], m['schema']) for m in metas}) == 1
            assert metas[0]['schema'] == schema and all(m['tester_allowed'] for m in metas)

            # Outsider denial precedes identity/wallet/financial side effects.
            before = await counts(pool)
            for body in ({'user': 900}, {'user': 900, 'callback': 'accept'},
                         {'user': 900, 'callback': 'history:0'}):
                status, result = await request(client, url_a + '/fixture/telegram', body=body)
                assert status == 200 and result['denied'] and not result['admin']
            assert (await request(client, url_m + '/api/v1/session', body={'initData': signed('fixture', 900)}))[0] == 403
            for path in ('/api/v1/wallet', '/api/v1/works', '/api/v1/admin', '/api/v1/jobs'):
                assert (await request(client, url_m + path))[0] in (401, 404, 405)
            assert before == await counts(pool)
            assert not await pool.fetchval('SELECT EXISTS(SELECT 1 FROM identities WHERE external_id=900)')
            assert not (await request(client, url_a + '/fixture/telegram', body={'user': 100}))[1]['denied']

            assert not (await request(client, url_a + '/fixture/telegram', body={'user': 101}))[1]['denied']
            assert not (await request(client, url_a + '/fixture/telegram', body={'user': 101, 'callback': 'accept'}))[1]['denied']
            tester = await pool.fetchval("SELECT user_id FROM identities WHERE platform='telegram' AND external_id=101")
            assert tester is not None
            own_work = await service.save_image_work(tester, -902, 'fixture/image', 'fixture',
                SimpleNamespace(image=MOCK_IMAGE, filename='fixture.png'))
            assert not (await request(client, url_b + '/fixture/telegram', body={'user': 101, 'callback': 'history:0'}))[1]['admin']
            raw = signed('fixture', 101)
            status, login = await request(client, url_m + '/api/v1/session', body={'initData': raw})
            assert status == 200
            headers = {'Authorization': 'Bearer ' + login['token']}
            assert (await request(client, url_m + '/api/v1/session', body={'initData': raw}))[0] == 401
            assert (await request(client, url_m + '/api/v1/wallet', headers=headers))[0] == 200
            assert (await request(client, url_m + '/api/v1/works', headers=headers))[0] == 200
            assert (await request(client, url_m + '/api/v1/works/image/' + str(own_work), headers=headers))[0] == 200
            assert (await request(client, url_m + '/api/v1/works/image/' + str(admin_work), headers=headers))[0] == 404
            assert (await request(client, url_m + '/api/v1/admin', headers=headers))[0] == 404
            assert (await request(client, url_m + '/api/v1/session', body={'initData': signed('fixture', 101, age=360)}))[0] == 401
            status, expiring = await request(client, url_m + '/api/v1/session', body={'initData': signed('fixture', 101, age=2)})
            assert status == 200
            await pool.execute("UPDATE miniapp_sessions SET expires_at=now()-interval '1 second' WHERE token_hash=$1", token_hash(expiring['token']))
            assert (await request(client, url_m + '/api/v1/wallet', headers={'Authorization': 'Bearer ' + expiring['token']}))[0] == 401

            # Config is a per-process snapshot. Replacing A does not update B or Mini App.
            financial_before = await counts(pool)
            revoked_at = time.monotonic()
            await stop_process(a)
            a, url_a = await launch('telegram', False)
            assert (await request(client, url_a + '/fixture/telegram', body={'user': 101, 'callback': 'history:0'}))[1]['denied']
            assert not (await request(client, url_b + '/fixture/telegram', body={'user': 101, 'callback': 'history:0'}))[1]['denied']
            assert (await request(client, url_m + '/api/v1/wallet', headers=headers))[0] == 200
            # Restart only Mini App: old session is denied there while B remains stale.
            await stop_process(mini)
            mini, url_m = await launch('miniapp', False)
            assert (await request(client, url_m + '/api/v1/wallet', headers=headers))[0] == 403
            assert not (await request(client, url_b + '/fixture/telegram', body={'user': 101, 'callback': 'history:0'}))[1]['denied']
            await stop_process(b)
            b, url_b = await launch('telegram', False)
            window = time.monotonic() - revoked_at
            callbacks = ('accept', 'providers', 'am', 'slist:current:video:0', 'history:0', 'image:' + str(admin_work))
            for url in (url_a, url_b):
                for callback in callbacks:
                    status, result = await request(client, url + '/fixture/telegram', body={'user': 101, 'callback': callback})
                    assert status == 200 and result['denied'] and not result['admin']
            simultaneous = await asyncio.gather(*(request(client, u + '/fixture/telegram', body={'user': 101, 'callback': 'history:0'}) for u in (url_a, url_b)))
            assert all(result[1]['denied'] for result in simultaneous)
            assert (await request(client, url_m + '/api/v1/wallet', headers=headers))[0] == 403
            assert (await request(client, url_m + '/api/v1/session', body={'initData': signed('fixture', 101, age=1)}))[0] == 403
            # A stopped process does not grant access through the refreshed B.
            await stop_process(a)
            assert (await request(client, url_b + '/fixture/telegram', body={'user': 101, 'callback': 'history:0'}))[1]['denied']
            assert financial_before == await counts(pool)
            assert await pool.fetchval('SELECT EXISTS(SELECT 1 FROM identities WHERE user_id=$1)', tester)
            assert await pool.fetchval("SELECT count(*) FROM wallets WHERE user_id=$1", tester) == 2
            print(f'MULTIPROCESS stale_window_seconds={window:.3f} processes=3 distinct_pids=3 shared_db=true side_effects_unchanged=true', flush=True)
    finally:
        for process in reversed(processes):
            await stop_process(process)
