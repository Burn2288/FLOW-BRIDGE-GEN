import hashlib
import hmac
import json
import time
from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer

from elevenbot.aggregate import make_snapshot
from elevenbot.anymodel import model_store
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.miniapp_web import create_app


def signed(token, user, age=0):
    fields = {'auth_date': str(int(time.time()) - age), 'user': json.dumps({'id': user})}
    data = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    key = hmac.digest(b'WebAppData', token.encode(), 'sha256')
    return urlencode(fields | {'hash': hmac.new(key, data.encode(), hashlib.sha256).hexdigest()})


async def test_miniapp_shared_wallet_library_and_session(env):
    pool, cfg, service, owner = env
    cfg = replace(cfg, token='fixture', interaction_mode='mock', access_mode='private',
                  anymodel_test_enabled=True, catalogue_path=str(cfg.storage.parent / 'catalogue.json'))
    models = [{'provider': 'clodex', 'id': name, 'title': name,
               'availability': 'key_available', 'operations': ['images.generate']}
              for name in ('fixture/image', 'fixture/unapproved')]
    SnapshotStore(cfg.catalogue_path).write(make_snapshot(models, [], [
        {'provider': 'clodex', 'scope': 'key_available'}
    ]))
    await pool.execute("INSERT INTO approved_models VALUES('clodex','fixture/image','images.generate','Image')")
    model_store(cfg).write(make_snapshot([
        {'provider': 'anymodel', 'id': 'anymedia/fibo-2', 'title': 'FIBO 2',
         'availability': 'key_available', 'operations': ['images.generate']}
    ], [], [{'provider': 'anymodel', 'scope': 'key_available'}]))
    stranger = await service.identity(101)
    await service.accept(stranger)
    work = await service.save_image_work(owner, -501, 'fixture/image', 'Fixture',
                                         SimpleNamespace(image=MOCK_IMAGE, filename='test.png'))

    async with TestClient(TestServer(create_app(pool, cfg))) as client:
        async def login(raw, status=200):
            response = await client.post('/api/v1/session', json={'initData': raw})
            assert response.status == status
            if status == 200:
                return {'Authorization': 'Bearer ' + (await response.json())['token']}

        raw = signed(cfg.token, 100)
        await login(signed('wrong', 100), 401)
        await login(signed(cfg.token, 100, age=360), 401)
        await login(signed(cfg.token, 102), 403)
        main = await login(raw)
        await login(raw, 401)
        other = await login(signed(cfg.token, 101))
        response = await client.get('/api/v1/wallet', headers=main)
        row = await service.wallet(owner)
        assert await response.json() == {key: str(row[key]) for key in ('available', 'reserved')}
        response = await client.get('/api/v1/works', headers=main)
        history = await service.history(owner)
        assert [(item['id'], item['kind']) for item in (await response.json())['works']] == [
            (str(item['id']), item['kind']) for item in history
        ]
        response = await client.get('/api/v1/catalogue', headers=main)
        assert response.status == 200
        assert [m['id'] for m in (await response.json())['models']] == ['fixture/image', 'anymedia/fibo-2']
        response = await client.get(f'/api/v1/works/image/{work}', headers=main)
        assert response.status == 200 and await response.read() == MOCK_IMAGE
        response = await client.get('/api/v1/wallet', headers=other)
        other_wallet = await service.wallet(stranger)
        assert await response.json() == {key: str(other_wallet[key]) for key in ('available', 'reserved')}
        assert await (await client.get('/api/v1/works', headers=other)).json() == {'works': []}
        assert await (await client.get('/api/v1/catalogue', headers=other)).json() == await (
            await client.get('/api/v1/catalogue', headers=main)).json()
        response = await client.get(f'/api/v1/works/image/{work}', headers=other)
        assert response.status == 404
        response = await client.delete('/api/v1/session', headers=main)
        assert response.status == 204
        assert (await client.get('/api/v1/wallet', headers=main)).status == 401
        await login(raw, 401)
        await pool.execute("UPDATE miniapp_sessions SET expires_at=now()")
        assert (await client.get('/api/v1/wallet', headers=other)).status == 401
