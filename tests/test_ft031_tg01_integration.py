"""Combined TG-01 and TG-03 against an isolated PostgreSQL schema."""
import hashlib
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from elevenbot.aggregate import make_snapshot
from elevenbot.db import migrate
from elevenbot.discovery import SnapshotStore
from elevenbot.telegram import TelegramApp
from scripts.disposable_test_db import require_disposable_dsn
from test_admin_access import event
from test_navigation import Transport


async def test_tg01_migration_preserves_navigation_and_checksums():
    dsn = require_disposable_dsn(os.environ)
    admin = await asyncpg.connect(dsn)
    schema = 'test_' + uuid4().hex
    pool = None
    try:
        await admin.execute(f'CREATE SCHEMA {schema}')
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2, server_settings={'search_path': schema})
        files = sorted((Path(__file__).resolve().parents[1] / 'migrations').glob('*.sql'))
        target = '042_telegram_panel_callbacks.sql'
        async with pool.acquire() as c, c.transaction():
            await c.execute('CREATE TABLE schema_migrations(version text PRIMARY KEY, sha256 text NOT NULL)')
            for f in files:
                if f.name == target:
                    continue
                sql = f.read_text(encoding='utf-8')
                await c.execute(sql)
                await c.execute('INSERT INTO schema_migrations VALUES($1,$2)', f.name, hashlib.sha256(sql.encode()).hexdigest())
            await c.execute("INSERT INTO telegram_navigation(chat_id,active_id) VALUES(991,123)")
        before = [tuple(r) for r in await pool.fetch('SELECT * FROM schema_migrations ORDER BY version')]
        await migrate(pool)
        assert await pool.fetchval('SELECT active_id FROM telegram_navigation WHERE chat_id=991') == 123
        expected = hashlib.sha256((Path(__file__).resolve().parents[1]/'migrations'/target).read_text(encoding='utf-8').encode()).hexdigest()
        assert await pool.fetchval('SELECT sha256 FROM schema_migrations WHERE version=$1', target) == expected
        assert [tuple(r) for r in await pool.fetch('SELECT * FROM schema_migrations WHERE version <> $1 ORDER BY version', target)] == before
        await pool.execute("INSERT INTO telegram_panel_callbacks VALUES(991,123,ARRAY['home'])")
        with pytest.raises(asyncpg.UniqueViolationError):
            await pool.execute("INSERT INTO telegram_panel_callbacks VALUES(991,123,ARRAY['home'])")
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await pool.execute("INSERT INTO telegram_panel_callbacks VALUES(992,123,ARRAY['home'])")
        await migrate(pool)
        assert await pool.fetchval('SELECT count(*) FROM schema_migrations') == len(before) + 1
        await pool.execute('DELETE FROM telegram_navigation WHERE chat_id=991')
        assert await pool.fetchval('SELECT count(*) FROM telegram_panel_callbacks WHERE chat_id=991') == 0
    finally:
        if pool:
            await pool.close()
        await admin.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
        await admin.close()


async def test_tg01_tg03_balance_history_round_trip(env, tmp_path):
    pool, cfg, _, owner = env
    cfg = replace(cfg, catalogue_path=str(tmp_path/'catalogue.json'))
    SnapshotStore(cfg.catalogue_path).write(make_snapshot([], [], [{'provider':'clodex','scope':'key_available'}]))
    bot = Transport(pool)
    app = TelegramApp(pool, cfg, bot)
    sequence = 1
    ledger = [tuple(row) for row in await pool.fetch('SELECT * FROM ledger ORDER BY id')]
    wallet = tuple(await pool.fetchrow('SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode=$2', owner, cfg.balance_wallet_mode))

    async def view():
        state = await app.navigation.read(100)
        _, text, markup = bot.messages[state.active_id]
        keys = {b.callback_data: b.text for row in markup.inline_keyboard for b in row}
        live = [mid for mid, (_, _, kb) in bot.messages.items() if hasattr(kb, 'inline_keyboard')]
        assert live == [state.active_id]
        assert await pool.fetchval('SELECT active_id FROM telegram_navigation WHERE chat_id=100') == state.active_id
        return state.active_id, text, keys

    async def press(screen, callback):
        nonlocal sequence
        assert callback in screen[2]
        sequence += 1
        await app.handle(event(sequence, callback=callback, source_message_id=screen[0]))
        return await view()

    await app.handle(event(sequence, '/menu'))
    main = await view()
    assert 'Выберите агрегатор' in main[1] and 'section:2' in main[2]
    balance = await press(main, 'section:2')
    assert 'Личный кабинет' in balance[1] and 'walletlog:0' in balance[2]
    history = await press(balance, 'walletlog:0')
    assert 'История операций' in history[1] and 'section:2' in history[2]
    back = await press(history, 'section:2')
    assert 'Личный кабинет' in back[1] and 'walletlog:0' in back[2] and 'home' in back[2]
    final = await press(back, 'home')
    assert final[1:] == main[1:]
    assert tuple(await pool.fetchrow('SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode=$2', owner, cfg.balance_wallet_mode)) == wallet
    assert [tuple(row) for row in await pool.fetch('SELECT * FROM ledger ORDER BY id')] == ledger
