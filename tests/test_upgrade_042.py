"""Upgrade a populated pre-refund database using the normal migrator."""
import os
import re
from pathlib import Path
from shutil import copyfile
from uuid import uuid4

import asyncpg

from elevenbot import db
from elevenbot.config import Config
from elevenbot.core import Service
from scripts.disposable_test_db import require_disposable_dsn
from test_topups import fixture, quote


async def test_existing_topup_survives_042(tmp_path, monkeypatch):
    dsn = require_disposable_dsn(os.environ)
    schema = 'upgrade_' + uuid4().hex
    root = Path(db.__file__).resolve().parents[2]
    historical = tmp_path / 'migrations'
    historical.mkdir()
    for sql in (root / 'migrations').glob('*.sql'):
        if int(sql.name[:3]) <= 41:
            copyfile(sql, historical / sql.name)
    admin = await asyncpg.connect(dsn)
    try:
        await admin.execute(f'CREATE SCHEMA {schema}')
        async with asyncpg.create_pool(dsn, server_settings={'search_path': schema}) as pool:
            with monkeypatch.context() as patch:
                patch.setattr(db, '__file__', str(tmp_path / 'src/elevenbot/db.py'))
                await db.migrate(pool)
            cfg = Config(storage=tmp_path/'media')
            svc = Service(pool, cfg)
            user = await svc.identity(100)
            await svc.accept(user)
            _, _, _, payments, _ = await fixture((pool, cfg, svc, user))
            try:
                order = await quote(payments, user)
                await payments.create(user, order['id'], test_session=True)
                await payments.check(user, order['id'])
            finally:
                await payments.client.close()

            async def kinds():
                definition = await pool.fetchval("""
                    SELECT pg_get_constraintdef(oid) FROM pg_constraint
                    WHERE conrelid='ledger'::regclass AND conname='ledger_kind_check'
                """)
                return set(re.findall("'([^']+)'", definition))

            async def snapshot():
                return (await pool.fetch("SELECT * FROM ledger WHERE user_id=$1 ORDER BY id", user),
                        await pool.fetch("SELECT * FROM wallets WHERE user_id=$1 ORDER BY mode", user))

            prior = await kinds()
            before = await snapshot()
            assert [r['da'] for r in before[0] if r['kind']=='topup'] == [1000]
            for _ in range(2):
                await db.migrate(pool)
                assert await kinds() == prior | {'task_refund', 'referral_reward', 'referral_reversal', 'referral_debt_repay'}
                assert await snapshot() == before
    finally:
        await admin.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        await admin.close()


async def test_funding_upgrade_from_047_preserves_wallets(tmp_path, monkeypatch):
    dsn = require_disposable_dsn(os.environ)
    schema = 'funding_upgrade_' + uuid4().hex
    root = Path(db.__file__).resolve().parents[2]
    historical = tmp_path / 'migrations'
    historical.mkdir()
    for sql in (root / 'migrations').glob('*.sql'):
        if int(sql.name[:3]) <= 47:
            copyfile(sql, historical / sql.name)
    admin = await asyncpg.connect(dsn)
    try:
        await admin.execute(f'CREATE SCHEMA {schema}')
        async with asyncpg.create_pool(dsn, server_settings={'search_path': schema}) as pool:
            with monkeypatch.context() as patch:
                patch.setattr(db, '__file__', str(tmp_path / 'src/elevenbot/db.py'))
                await db.migrate(pool)
            cfg = Config(generation_enabled=True, storage=tmp_path/'media')
            svc = Service(pool, cfg)
            for external in (100, 101):
                user = await svc.identity(external)
                await svc.accept(user)
                order, _ = await svc.quote(user, 'hello', 'demo')
                await svc.confirm(user, order)
            user = await svc.identity(100)
            _, _, _, payments, _ = await fixture((pool, cfg, svc, user))
            try:
                order = await quote(payments, user)
                await payments.create(user, order['id'], test_session=True)
                await payments.check(user, order['id'])
                before_wallets = await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode')
                before_ledger = await pool.fetch('SELECT * FROM ledger ORDER BY id')
                assert any(row['reserved'] > 0 for row in before_wallets)
                for _ in range(2):
                    await db.migrate(pool)
                    assert await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode') == before_wallets
                    assert await pool.fetch('SELECT * FROM ledger ORDER BY id') == before_ledger
                    lots = await pool.fetch('SELECT user_id,mode,origin,available FROM wallet_funding_lots')
                    assert {tuple(row) for row in lots} == {
                        (row['user_id'], row['mode'], 'UNKNOWN_LEGACY', row['available'])
                        for row in before_wallets if row['available'] > 0
                    }
            finally:
                await payments.client.close()
    finally:
        await admin.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        await admin.close()
