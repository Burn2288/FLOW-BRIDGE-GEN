"""One full-database disposable native backup, with combined candidate data."""
import hashlib
import json
import os
from dataclasses import replace
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import asyncpg
import pytest

from elevenbot.config import Config
from elevenbot.core import Rejected, Service
from elevenbot.database_setup import identifier, provision
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.providers import MockProvider
from elevenbot.snapshot import backup, restore_drill, verify
from elevenbot.telegram import TelegramApp
from elevenbot.worker import Worker
from scripts.disposable_test_db import require_disposable_dsn
from test_ft020_http_image import image_api, quote, create
from test_ui import Bot


@pytest.fixture
async def account_db(tmp_path):
    dsn = require_disposable_dsn(os.environ)
    url = urlsplit(dsn)
    name = 'darkflow_backup_' + uuid4().hex[:12]
    folder = tmp_path / 'private'
    admin = await asyncpg.connect(dsn)
    roles = []
    try:
        await provision(url.hostname, url.port or 5432, unquote(url.username), unquote(url.password or ''), name, folder)
        creds = json.loads((folder / 'database.credentials.json').read_text())
        roles = [urlsplit(creds[k]).username for k in ('DATABASE_URL', 'DATABASE_MIGRATION_URL')]
        cfg = Config(token='fixture', interaction_mode='mock', access_mode='private', admin_ids=(100,),
                     pilot_user_ids=(101, 102), anymodel_test_enabled=True, storage=tmp_path/'audio',
                     catalogue_path=str(tmp_path/'catalogue.json'))
        async with asyncpg.create_pool(creds['DATABASE_URL'], min_size=1, max_size=4) as pool:
            yield pool, cfg
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS {identifier(name)} WITH (FORCE)')
        for role in roles:await admin.execute(f'DROP ROLE {identifier(role)}')
        await admin.close()


async def test_full_backup_restore_of_combined_candidate(image_api, account_db, tmp_path):
    pool, users, client, headers, posts, deferred, _, _ = image_api
    _, cfg = account_db
    service = Service(pool, cfg)
    code = (await service.referral_info(users[0]))['code']
    invited = await service.identity(102, referral_code=code)
    await service.accept(invited)
    app = TelegramApp(pool, cfg, Bot())
    await pool.execute("INSERT INTO approved_models VALUES('clodex','flux-schnell','images.generate','FLUX Schnell') ON CONFLICT DO NOTHING")
    schema = {'properties': {'n': {'type': 'integer', 'minimum': 1, 'maximum': 1}}, 'required': ['n']}
    version = await app.models.stage_capabilities(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', schema)
    await app.models.publish_capabilities(users[0], 100, 'clodex', 'flux-schnell', 'images.generate', version)
    q = await quote(client, headers[0])
    assert (await create(client, headers[0], q)).status == 201
    await deferred.pop()()
    assert posts == ['/v1/images/generations']
    image = await pool.fetchval('''SELECT w.id FROM image_works w JOIN http_image_commands h
                                   ON h.correlation_id=w.update_id WHERE h.quote_id=$1::uuid''', q)
    assert image is not None
    # Synthetic provider evidence: no provider or payment endpoint is contacted.
    await pool.execute("""INSERT INTO task_financial_receipts(provider,operation_id,provider_job_id,quote_id,outcome,amount,unit)
                          VALUES('clodex','fixture-operation','fixture-provider-job',$1::uuid,'charged',10,'darkflow_token')""", q)
    audio_cfg = replace(cfg, mode='mock', generation_enabled=True, access_mode='public')
    audio_svc = Service(pool, audio_cfg)
    await audio_svc.accept(users[0])  # existing demo grant, isolated fixture only
    aq, _ = await audio_svc.quote(users[0], 'backup fixture', 'demo')
    job = await audio_svc.confirm(users[0], aq)
    await Worker(pool, audio_cfg, MockProvider()).run_one()
    assert (await audio_svc.owned(users[0], job))['status'] == 'succeeded'
    audio_row = await pool.fetchrow('SELECT storage_key,sha256 FROM files WHERE job_id=$1', job)
    audio_bytes = (tmp_path/'audio'/audio_row['storage_key']).read_bytes()
    catalogue_bytes = (tmp_path/'catalogue.json').read_bytes()
    creds = json.loads((tmp_path/'private/database.credentials.json').read_text())
    runtime = tmp_path/'runtime.env'
    runtime.write_text('DATABASE_URL='+creds['DATABASE_URL']+'\nAUDIO_STORAGE_DIR=audio\nCATALOGUE_PATH=catalogue.json\n', encoding='utf-8')
    target = tmp_path/'backup'
    assert (await backup(runtime, target))['catalogue_present']
    bad_runtime = tmp_path/'bad.env'
    bad_runtime.write_text('DATABASE_URL='+creds['DATABASE_URL']+'\nAUDIO_STORAGE_DIR=audio\nCATALOGUE_PATH=bad.env\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Runtime configuration'):
        await backup(bad_runtime, tmp_path/'bad-backup')
    assert not (tmp_path/'bad-backup/catalogue/models.json').exists()
    manifest = verify(target)
    assert manifest['catalogue']['present'] and manifest['files']['catalogue/models.json'] == hashlib.sha256(catalogue_bytes).hexdigest()
    tables = ('identities', 'wallets', 'ledger', 'referral_codes', 'referral_attributions',
              'model_capability_versions', 'task_price_quotes', 'http_image_commands', 'task_financial_receipts')
    async def snapshot(p):
        return {table: sorted((dict(row) for row in await p.fetch('SELECT * FROM '+table)), key=str) for table in tables}
    before = await snapshot(pool)
    async def check(restored, root):
        assert await restored.fetchval('SELECT halted FROM settings WHERE id=1')
        assert await snapshot(restored) == before
        assert await restored.fetchval('SELECT referrer_id FROM referral_attributions WHERE user_id=$1', invited) == users[0]
        assert await restored.fetchval('SELECT code FROM referral_codes WHERE user_id=$1', users[0]) == code
        restored_svc = Service(restored, replace(cfg, storage=root/'audio'))
        assert (await restored_svc.image_work(users[0], image))['image'] == MOCK_IMAGE
        with pytest.raises(Rejected):await restored_svc.image_work(users[1], image)
        assert (await restored_svc.audio_work(users[0], job))['audio'] == audio_bytes
        with pytest.raises(Rejected):await restored_svc.audio_work(users[1], job)
        assert (root/'catalogue/models.json').read_bytes() == catalogue_bytes
        assert hashlib.sha256(audio_bytes).hexdigest() == audio_row['sha256']
    url = urlsplit(require_disposable_dsn(os.environ))
    kwargs = dict(migration_config=tmp_path/'private/migration.env', password=unquote(url.password or ''), admin_user=unquote(url.username), validator=check)
    admin = await asyncpg.connect(require_disposable_dsn(os.environ))
    try:
        prior = set(await admin.fetch('SELECT datname FROM pg_database WHERE datname LIKE \'darkflow_restore_%\''))
        result = await restore_drill(target, **kwargs)
        assert result['catalogue_hash_verified'] and result['restored_copy_halted'] and result['scratch_database_removed']
        assert set(await admin.fetch('SELECT datname FROM pg_database WHERE datname LIKE \'darkflow_restore_%\'')) == prior
        async def fail(_pool, _root):raise RuntimeError('fixture validation failure')
        with pytest.raises(RuntimeError, match='fixture validation failure'):
            await restore_drill(target, **(kwargs | {'validator': fail}))
        assert set(await admin.fetch('SELECT datname FROM pg_database WHERE datname LIKE \'darkflow_restore_%\'')) == prior
        assert await snapshot(pool) == before
        for path in (target/'catalogue/models.json', target/'audio'/audio_row['storage_key']):
            original = path.read_bytes()
            path.write_bytes(b'corrupt')
            with pytest.raises(ValueError, match='integrity'):await restore_drill(target, **kwargs)
            path.write_bytes(original)
    finally:
        await admin.close()
