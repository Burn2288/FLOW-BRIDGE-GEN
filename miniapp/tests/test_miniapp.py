import hashlib
import hmac
import json
import os
import time
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4
from unittest.mock import AsyncMock

import asyncpg
import pytest

from elevenbot.config import Config
from elevenbot.db import migrate

from aiohttp.test_utils import TestClient, TestServer

from elevenbot.aggregate import make_snapshot
from elevenbot.anymodel import model_store
from elevenbot.discovery import SnapshotStore
from elevenbot.core import Service
from elevenbot.interaction import MOCK_IMAGE
from miniapp.backend.web import create_app


def signed(token, user, age=0):
    fields = {'auth_date': str(int(time.time()) - age), 'user': json.dumps({'id': user})}
    data = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    key = hmac.digest(b'WebAppData', token.encode(), 'sha256')
    return urlencode(fields | {'hash': hmac.new(key, data.encode(), hashlib.sha256).hexdigest()})


@pytest.fixture
async def account_db(tmp_path):
    dsn = os.getenv('TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Separate PostgreSQL TEST_DATABASE_URL is required')
    schema = 'miniapp_' + uuid4().hex
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(f'CREATE SCHEMA {schema}')
        try:
            async with asyncpg.create_pool(dsn, server_settings={'search_path': schema}) as pool:
                await migrate(pool)
                cfg = Config(token='fixture', interaction_mode='mock', access_mode='private',
                             anymodel_test_enabled=True, catalogue_path=str(tmp_path / 'catalogue.json'))
                yield pool, cfg
        finally:
            await connection.execute(f'DROP SCHEMA {schema} CASCADE')
    finally:
        await connection.close()


async def test_miniapp_shared_wallet_library_and_session(account_db):
    pool, cfg = account_db
    service = Service(pool, cfg)
    owner = await service.identity(100)
    await service.accept(owner)
    async with pool.acquire() as conn, conn.transaction():
        await service.movement(conn, owner, 'live', 'miniapp-test-credit', 'pilot_grant', 1200, 0)
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

        for path, marker in (
            ('/', 'data-panel="catalogue"'), ('/assets/app.js', 'applyTheme'),
            ('/assets/style.css', 'data-theme="light"')
        ):
            response = await client.get(path)
            assert response.status == 200 and marker in await response.text()
        banner = await client.get('/assets/darkflow-banner.png')
        assert banner.status == 200 and (await banner.read()).startswith(b'\x89PNG')

        raw = signed(cfg.token, 100)
        await login(signed('wrong', 100), 401)
        await login(signed(cfg.token, 100, age=360), 401)
        await login(signed(cfg.token, 102), 403)
        main = await login(raw)
        await login(raw, 401)
        other = await login(signed(cfg.token, 101))
        settings = '/api/v1/settings'
        assert await (await client.get(settings, headers=main)).json() == {'theme': 'dark'}
        response = await client.put(settings, headers=main, json={'theme': 'light'})
        assert await response.json() == {'theme': 'light'}
        assert (await client.put(settings, headers=other, json={'theme': 'auto'})).status == 400
        assert (await client.put(settings, headers=other, json={'theme': 'light', 'user': 100})).status == 400
        assert (await client.put(settings, json={'theme': 'light'})).status == 401
        assert await (await client.get(settings, headers=other)).json() == {'theme': 'dark'}
        second_device = await login(signed(cfg.token, 100, age=1))
        assert await (await client.get(settings, headers=second_device)).json() == {'theme': 'light'}
        assert (await client.put(settings, headers=second_device, json={'theme': 'dark'})).status == 200
        assert await (await client.get(settings, headers=main)).json() == {'theme': 'dark'}
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


async def test_telegram_menu_button():
    from elevenbot.telegram import register_miniapp_menu

    bot = AsyncMock()
    await register_miniapp_menu(bot, 'https://miniapp.example.test/')
    button = bot.set_chat_menu_button.await_args.kwargs['menu_button']
    assert button.type == 'web_app'
    assert button.text == 'Приложение'
    assert button.web_app.url == 'https://miniapp.example.test/'
