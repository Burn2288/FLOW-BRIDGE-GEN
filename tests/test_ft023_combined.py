"""Cross-package checks on the actual HTTP and PostgreSQL paths."""
import json
from copy import deepcopy
from dataclasses import replace

from elevenbot.aggregate import ProviderRegistry
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.provider_lifecycle import MockManifestProbe
from elevenbot.telegram import TelegramApp
from miniapp.tests.test_miniapp import account_db
from test_ft020_http_image import image_api, quote, create
from test_provider_manifest import MockAdapter, manifest
from test_ui import Bot


def test_registry_keeps_lifecycle_and_financial_adapters_together():
    registry = ProviderRegistry()
    price, launch, lookup = object(), object(), object()
    registry.register('clodex', MockAdapter(), price=price, launch=launch, financial_lookup=lookup)
    data = manifest('clodex', 'clodex', 'CLODEX_API_KEY', 'https://clodex.xyz/v1/chat/completions')
    registry.load_manifest(data)
    version = registry.lifecycle.stage(data, MockManifestProbe())['version']
    registry.lifecycle.activate('clodex', version)
    assert registry.lifecycle.pin('clodex', 'fixture/model')['version'] == version
    assert registry.manifests['clodex']['status'] == 'METADATA_VALIDATED'
    assert registry.prices['clodex'] is price
    assert registry.launches['clodex'] is launch
    assert registry.financial_sources['clodex'] is lookup


async def test_http_quote_retains_model_version_and_price_across_updates(image_api, account_db):
    pool, users, client, headers, posts, deferred, _, _ = image_api
    _, original = account_db
    cfg = replace(original, mode='clodex', generation_enabled=True, economy_verified=True,
                  clodex_key='fixture-only', interaction_mode='off', interaction_limit=100,
                  public_image_models=('clodex:flux-schnell',), payments_enabled=False)
    app = TelegramApp(pool, cfg, Bot())
    await pool.execute("INSERT INTO approved_models VALUES('clodex','flux-schnell','images.generate','FLUX Schnell') ON CONFLICT DO NOTHING")
    schema_a = {'properties': {'n': {'type': 'integer', 'minimum': 1, 'maximum': 1}}, 'required': ['n']}
    a = await app.models.stage_capabilities(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', schema_a)
    await app.models.publish_capabilities(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', a)
    async def tariff(amount):
        await app.pricing.set_tariff(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', {'n': 1},
                                     basis='request', unit='darkflow_token', amount=amount, expires=None, evidence='fixture')
    await tariff('60')
    q = await quote(client, headers[0])
    row = await pool.fetchrow('SELECT request::text, price::text FROM task_price_quotes WHERE id=$1::uuid', q)
    assert json.loads(row['request'])['model_version'] == {'version': str(a), 'schema': schema_a}
    assert json.loads(row['price'])['total'] == '60'
    schema_b = deepcopy(schema_a)
    schema_b['properties']['n']['maximum'] = 2
    b = await app.models.stage_capabilities(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', schema_b)
    await app.models.publish_capabilities(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', b)
    await tariff('85')
    response = await create(client, headers[0], q)
    assert response.status == 201, await response.text()
    assert (await create(client, headers[0], q)).status == 200
    assert len(deferred) == 1
    await deferred.pop()()
    assert posts == ['/v1/images/generations']
    data = await (await client.get('/api/v1/jobs/' + q, headers=headers[0])).json()
    assert data['state'] == 'completed'
    assert await (await client.get(data['result_url'], headers=headers[0])).read() == MOCK_IMAGE
    assert (await client.get(data['result_url'], headers=headers[1])).status == 404
    rows = await pool.fetch('SELECT kind,da,dr FROM ledger WHERE task_quote_id=$1::uuid ORDER BY kind', q)
    assert [(r['kind'], r['da'], r['dr']) for r in rows] == [('task_capture', 0, -60), ('task_reserve', -60, 60)]
    saved = await pool.fetchrow('SELECT request::text, price::text FROM task_price_quotes WHERE id=$1::uuid', q)
    assert json.loads(saved['request'])['model_version'] == {'version': str(a), 'schema': schema_a}
    assert json.loads(saved['price'])['total'] == '60'
    following = await quote(client, headers[0], 'next fixture')
    row = await pool.fetchrow('SELECT request::text, price::text FROM task_price_quotes WHERE id=$1::uuid', following)
    assert json.loads(row['request'])['model_version'] == {'version': str(b), 'schema': schema_b}
    assert json.loads(row['price'])['total'] == '85'


async def test_upgrade_from_041_preserves_existing_wallet_and_both_042(tmp_path, monkeypatch):
    import os
    from pathlib import Path
    from shutil import copyfile
    from uuid import uuid4
    import asyncpg
    from elevenbot import db
    from elevenbot.config import Config
    from elevenbot.core import Service
    from scripts.disposable_test_db import require_disposable_dsn

    dsn = require_disposable_dsn(os.environ)
    schema = 'upgrade_' + uuid4().hex
    root = Path(db.__file__).resolve().parents[2]
    old = tmp_path / 'migrations'
    old.mkdir()
    for sql in (root / 'migrations').glob('*.sql'):
        if int(sql.name[:3]) <= 41:
            copyfile(sql, old / sql.name)
    admin = await asyncpg.connect(dsn)
    try:
        await admin.execute(f'CREATE SCHEMA {schema}')
        async with asyncpg.create_pool(dsn, server_settings={'search_path': schema}) as pool:
            with monkeypatch.context() as patch:
                patch.setattr(db, '__file__', str(tmp_path / 'src/elevenbot/db.py'))
                await db.migrate(pool)
            svc = Service(pool, Config(storage=tmp_path / 'media'))
            user = await svc.identity(100)
            await svc.accept(user)
            async with pool.acquire() as conn, conn.transaction():
                await svc.movement(conn, user, 'live', 'ft023-upgrade-credit', 'pilot_grant', 100, 0)
            before = (await pool.fetch('SELECT * FROM identities ORDER BY user_id'),
                      await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode'),
                      await pool.fetch('SELECT * FROM ledger ORDER BY id'))
            await db.migrate(pool)
            await db.migrate(pool)
            after = (await pool.fetch('SELECT * FROM identities ORDER BY user_id'),
                     await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode'),
                     await pool.fetch('SELECT * FROM ledger ORDER BY id'))
            assert before == after
            names = {r['version'] for r in await pool.fetch('SELECT version FROM schema_migrations')}
            assert {'042_model_capability_versions.sql', '042_task_financial_receipts.sql',
                    '043_http_image_commands.sql', '044_referral_attribution.sql'} <= names
    finally:
        await admin.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        await admin.close()
