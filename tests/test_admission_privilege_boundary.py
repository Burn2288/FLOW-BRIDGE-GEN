"""Real disposable cluster roles; no production bootstrap or route integration."""
import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
import pytest_asyncio

from elevenbot.admission_store import PolicyDenied, VersionConflict, replace_policy, require_on
from scripts.disposable_test_db import require_disposable_dsn
from verification.admission_test_privileges import setup_test_acl, TABLES


async def allowed(conn, actor):
    return actor == 100


async def denied(conn, actor):
    return False


@pytest_asyncio.fixture
async def privilege_env(env):
    pool, _, _, _ = env
    dsn = require_disposable_dsn(os.environ)
    schema = await pool.fetchval('SELECT current_schema()')
    suffix = uuid.uuid4().hex
    migration, runtime, policy = ('tq_m_'+suffix, 'tq_r_'+suffix, 'tq_p_'+suffix)
    names = (migration, runtime, policy)
    role_pools = []
    created = []
    try:
        async with pool.acquire() as conn:
            for role in names:
                await conn.execute(f"CREATE ROLE {role} LOGIN PASSWORD 'fixture-only-policy' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
                created.append(role)
            # Simulate the overbroad default application grants being explicitly removed.
            for table in TABLES:
                await conn.execute(f'GRANT ALL ON {schema}.{table} TO {runtime}')
            await setup_test_acl(conn, schema, migration, runtime, policy)
        parts = urlsplit(dsn)
        for role in (runtime, policy):
            role_dsn = urlunsplit(parts._replace(netloc=f'{role}:fixture-only-policy@{parts.hostname}:{parts.port}'))
            role_pools.append(await asyncpg.create_pool(role_dsn, min_size=1, max_size=4,
                                                       server_settings={'search_path': schema}))
        yield pool, schema, names, role_pools[0], role_pools[1]
    finally:
        for item in role_pools:
            await item.close()
        async with pool.acquire() as conn:
            # Return ownership before dropping only the generated roles.
            if migration in created:
                for table in TABLES:
                    if await conn.fetchval('SELECT to_regclass($1) IS NOT NULL', f'{schema}.{table}'):
                        await conn.execute(f'ALTER TABLE {schema}.{table} OWNER TO postgres')
                await conn.execute(f'ALTER FUNCTION {schema}.admission_shadow_audit_immutable() OWNER TO postgres')
            for role in reversed(created):
                await conn.execute(f'DROP OWNED BY {role}')
                await conn.execute(f'DROP ROLE {role}')


async def snapshot(pool):
    return (tuple(await pool.fetchrow('SELECT version,initialized FROM admission_policy_shadow')),
            [tuple(r) for r in await pool.fetch('SELECT telegram_id,role FROM admission_membership_shadow ORDER BY telegram_id')],
            [tuple(r) for r in await pool.fetch('SELECT operation_id,actor_telegram_id,version,payload_sha256 FROM admission_policy_audit_shadow ORDER BY version')])


async def test_runtime_direct_sql_denied_without_state_change(privilege_env):
    pool, schema, (migration, runtime, policy), runtime_pool, policy_pool = privilege_env
    await replace_policy(policy_pool, expected_version=0, operation_id=uuid.uuid4(), actor=100,
                         admins=(100,), testers=(101,), authorize_admin=allowed)
    before = await snapshot(pool)
    denied_sql = [
        "INSERT INTO admission_membership_shadow VALUES(102,'tester')",
        "INSERT INTO admission_membership_shadow VALUES(103,'admin')",
        "UPDATE admission_membership_shadow SET role='admin' WHERE telegram_id=101",
        "DELETE FROM admission_membership_shadow WHERE telegram_id=100",
        'UPDATE admission_policy_shadow SET version=version+1',
        "INSERT INTO admission_policy_audit_shadow VALUES(gen_random_uuid(),100,999,repeat('a',64),now())",
        'DELETE FROM admission_policy_audit_shadow',
        "UPDATE admission_policy_audit_shadow SET payload_sha256=repeat('b',64)",
        'ALTER TABLE admission_policy_audit_shadow DISABLE TRIGGER admission_shadow_audit_no_update',
        'ALTER FUNCTION admission_shadow_audit_immutable() RENAME TO fixture_renamed',
        f'ALTER SCHEMA {schema} OWNER TO {runtime}',
        f'GRANT {migration} TO {runtime}',
    ]
    async with runtime_pool.acquire() as conn:
        assert await conn.fetchval('SELECT current_user') == runtime
        assert await conn.fetchval('SELECT version FROM admission_policy_shadow') == 1
        assert not await conn.fetchval('SELECT pg_has_role(current_user,$1,\'MEMBER\')', migration)
        for sql in denied_sql:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(sql)
            assert await snapshot(pool) == before
        # PostgreSQL row locks require UPDATE; SELECT-only runtime cannot use this prototype.
        async with conn.transaction():
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await require_on(conn, 101)
    assert not await pool.fetchval("""SELECT EXISTS (SELECT 1 FROM pg_class c
        CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
        WHERE c.oid=$1::regclass AND a.grantee=0 AND a.privilege_type='INSERT')""",
        f'{schema}.admission_membership_shadow')


async def test_trusted_fixture_updates_conflicts_and_rollback(privilege_env):
    pool, _, _, _, policy_pool = privilege_env
    async def update(version, op, members=(101,), authorizer=allowed):
        return await replace_policy(policy_pool, expected_version=version, operation_id=op,
                                    actor=100, admins=(100,), testers=members, authorize_admin=authorizer)
    first = uuid.uuid4()
    assert await update(0, first) == 1
    assert await update(0, first) == 1  # lost successful response / replay
    with pytest.raises(VersionConflict):
        await update(0, first, (102,))
    with pytest.raises(PolicyDenied):
        await update(1, uuid.uuid4(), authorizer=denied)
    results = await asyncio.gather(update(1, uuid.uuid4(), (102,)), update(1, uuid.uuid4(), (103,)), return_exceptions=True)
    assert sum(result == 2 for result in results) == 1
    assert sum(isinstance(result, VersionConflict) for result in results) == 1
    before = await snapshot(pool)
    async with policy_pool.acquire() as conn:
        transaction = conn.transaction()
        await transaction.start()
        await conn.execute('UPDATE admission_policy_shadow SET version=99')
        await transaction.rollback()
    assert await snapshot(pool) == before


async def test_populated_backup_restore_requires_acl_reapplication(privilege_env):
    pool, schema, (migration, runtime, policy), _, policy_pool = privilege_env
    first, second = uuid.uuid4(), uuid.uuid4()
    for expected, op, admins, testers in ((0, first, (100, 200), (101, 102)),
                                           (1, second, (100, 200), (102, 103))):
        await replace_policy(policy_pool, expected_version=expected, operation_id=op, actor=100,
                             admins=admins, testers=testers, authorize_admin=allowed)
    assert await replace_policy(policy_pool, expected_version=1, operation_id=second, actor=100,
                                admins=(100, 200), testers=(102, 103), authorize_admin=allowed) == 2
    expected = await snapshot(pool)
    source = urlsplit(require_disposable_dsn(os.environ))
    dbname = 'tq_restore_' + uuid.uuid4().hex
    pg_env = os.environ | {'PGHOST': source.hostname, 'PGPORT': str(source.port),
                           'PGUSER': source.username, 'PGPASSWORD': source.password,
                           'PGDATABASE': source.path.lstrip('/')}
    created = False
    restored = None
    try:
        await pool.execute(f'CREATE DATABASE {dbname}')
        created = True
        dump = await asyncio.create_subprocess_exec('pg_dump', '-Fc', '--no-owner', '--no-acl', '-n', schema,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=pg_env)
        payload, _ = await dump.communicate()
        assert dump.returncode == 0, 'test backup failed (details withheld)'
        restore = await asyncio.create_subprocess_exec('pg_restore', '--no-owner', '--no-acl', '--exit-on-error', '-d', dbname,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=pg_env)
        await restore.communicate(payload)
        assert restore.returncode == 0, 'test restore failed (details withheld)'
        target = urlunsplit(source._replace(path='/' + dbname))
        restored = await asyncpg.create_pool(target, min_size=1, max_size=2, server_settings={'search_path': schema})
        assert await snapshot(restored) == expected
        async with restored.acquire() as conn:
            await setup_test_acl(conn, schema, migration, runtime, policy)
        parts = source._replace(netloc=f'{runtime}:fixture-only-policy@{source.hostname}:{source.port}', path='/' + dbname)
        restricted = await asyncpg.connect(urlunsplit(parts), server_settings={'search_path': schema})
        try:
            assert await restricted.fetchval('SELECT version FROM admission_policy_shadow') == 2
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await restricted.execute("INSERT INTO admission_membership_shadow VALUES(777,'admin')")
        finally:
            await restricted.close()
        assert await snapshot(restored) == expected
    finally:
        if restored:
            await restored.close()
        if created:
            await pool.execute(f'DROP DATABASE {dbname} WITH (FORCE)')

async def test_http_admin_runtime_role_is_read_only(privilege_env,env):
    pool, schema, (_, runtime, _), runtime_pool, _ = privilege_env
    _, _, _, user = env
    await pool.execute(f'GRANT SELECT ON {schema}.http_admin_role_events TO {runtime}')
    assert await runtime_pool.fetchval('SELECT count(*) FROM http_admin_role_events') == 0
    for statement in (
        "INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason) VALUES($1,$1,'OWNER_ADMIN','fixture')",
        "UPDATE http_admin_role_events SET role='OWNER_ADMIN' WHERE subject_id=$1",
        'DELETE FROM http_admin_role_events WHERE subject_id=$1',
        "SELECT change_http_admin_role($1,$1,'OWNER_ADMIN',0,gen_random_uuid(),'fixture')",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await runtime_pool.execute(statement,user)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await runtime_pool.fetchval("SELECT nextval('http_admin_role_events_revision_seq')")
    assert await pool.fetchval('SELECT count(*) FROM http_admin_role_events') == 0
