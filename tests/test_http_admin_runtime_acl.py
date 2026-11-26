"""Check an upgrade under the Compose app principal's default privileges."""

import os
from pathlib import Path
from shutil import copyfile
from uuid import uuid4

import asyncpg
import pytest

from elevenbot import db
from elevenbot.config import Config
from elevenbot.core import Service
from elevenbot.model_visibility import confirm
from elevenbot.support_tickets import SupportTickets, operator_reply
from scripts.disposable_test_db import require_disposable_dsn


async def test_compose_runtime_cannot_write_role_history_after_upgrade(tmp_path, monkeypatch):
    dsn = require_disposable_dsn(os.environ)
    owner = await asyncpg.connect(dsn)
    schema = 'http_admin_acl_' + uuid4().hex
    created = False
    pool = None
    try:
        if await owner.fetchval("SELECT to_regrole('elevenbot_app') IS NOT NULL"):
            pytest.skip('This regression requires a disposable cluster without a pre-existing app role')
        await owner.execute('CREATE ROLE elevenbot_app NOSUPERUSER NOCREATEDB NOCREATEROLE')
        created = True
        # Match the initializer's default grants in this test's isolated schema.
        await owner.execute(f'''
            CREATE SCHEMA {schema};
            GRANT USAGE ON SCHEMA {schema} TO elevenbot_app;
            ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
                GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO elevenbot_app;
            ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
                GRANT USAGE,SELECT ON SEQUENCES TO elevenbot_app;
        ''')
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, server_settings={'search_path': schema})
        version = '062_http_admin_runtime_acl.sql'
        previous_migrations = tmp_path / 'migrations'
        previous_migrations.mkdir()
        for path in (Path(db.__file__).resolve().parents[2] / 'migrations').glob('*.sql'):
            if path.name < version:
                copyfile(path, previous_migrations / path.name)
        with monkeypatch.context() as old:
            old.setattr(db, '__file__', str(tmp_path / 'src/elevenbot/db.py'))
            await db.migrate(pool)

        assert await pool.fetchval(
            "SELECT has_table_privilege('elevenbot_app', 'http_admin_role_events', 'INSERT')"
        )
        assert await pool.fetchval(
            "SELECT has_sequence_privilege('elevenbot_app', 'http_admin_role_events_revision_seq', 'USAGE')"
        )
        await db.migrate(pool)
        assert await pool.fetchval('SELECT 1 FROM schema_migrations WHERE version=$1', version) == 1

        cfg = Config()
        service = Service(pool, cfg)
        actor = await service.identity(100)
        user = await service.identity(101)
        granted = await pool.fetchval("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,'OWNER_ADMIN','synthetic bootstrap') RETURNING revision
        """, actor)
        assert granted > 0
        assert await pool.fetchval("""
            SELECT change_http_admin_role($1,$2,'SUPPORT_OPERATOR',0,$3,'synthetic delegation')
        """, user, actor, uuid4()) > granted
        ticket = await SupportTickets(pool, cfg).create(101, uuid4(), 'Synthetic support ticket')

        async with pool.acquire() as conn:
            await conn.execute('SET ROLE elevenbot_app')
            assert await conn.fetchval("SELECT current_user = 'elevenbot_app'")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute("""
                    INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
                    VALUES($1,$1,'OWNER_ADMIN','synthetic unauthorized write')
                """, user)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute('DELETE FROM http_admin_role_events')
            with pytest.raises(asyncpg.RaiseError, match='immutable'):
                await conn.execute("UPDATE http_admin_role_events SET reason='changed'")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetchval("SELECT nextval('http_admin_role_events_revision_seq')")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.fetchval("""
                    SELECT change_http_admin_role($1,$2,NULL,0,$3,'synthetic unauthorized revocation')
                """, user, actor, uuid4())
            async with conn.transaction():
                changed = await confirm(conn, actor, 'clodex', 'flux-schnell', 'images.generate', 'HIDDEN', 0, uuid4())
                assert changed['visibility'] == 'HIDDEN'
                assert await operator_reply(conn, actor, ticket['id'], uuid4(), 'Synthetic operator reply')
        assert await pool.fetchval('SELECT count(*) FROM http_admin_role_events') == 2
    finally:
        if pool is not None:
            await pool.close()
        if created:
            await owner.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
            await owner.execute('DROP OWNED BY elevenbot_app')
            await owner.execute('DROP ROLE elevenbot_app')
        await owner.close()
