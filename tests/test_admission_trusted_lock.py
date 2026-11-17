"""Restricted-role PostgreSQL prototype; not wired to runtime admission."""
import asyncio
import uuid
import asyncpg
import pytest
import pytest_asyncio

from elevenbot.admission_store import VersionConflict, replace_policy
from test_admission_privilege_boundary import privilege_env, snapshot, allowed  # noqa: F401
from verification.admission_trusted_lock_fixture import install


@pytest_asyncio.fixture
async def trusted_env(privilege_env):
    pool, schema, names, runtime_pool, policy_pool = privilege_env
    function_owner = 'tq_f_' + uuid.uuid4().hex
    created = False
    try:
        async with pool.acquire() as conn:
            await conn.execute(f'CREATE ROLE {function_owner} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT')
            created = True
            await install(conn, schema, function_owner, names[1])
        yield pool, schema, names, function_owner, runtime_pool, policy_pool
    finally:
        if created:
            async with pool.acquire() as conn:
                await conn.execute(f'DROP FUNCTION IF EXISTS {schema}.fixture_admission_lock(bigint)')
                await conn.execute(f'DROP OWNED BY {function_owner}')
                await conn.execute(f'DROP ROLE {function_owner}')


async def update(pool, expected, *, testers=(101,), operation=None):
    return await replace_policy(pool, expected_version=expected, operation_id=operation or uuid.uuid4(),
                                actor=100, admins=(100,), testers=testers, authorize_admin=allowed)


async def test_definer_acl_and_uninitialized_fail_closed(trusted_env):
    pool, schema, (_, runtime, _), owner, runtime_pool, _ = trusted_env
    async with runtime_pool.acquire() as conn:
        assert await conn.fetchval('SELECT current_user') == runtime
        assert not await conn.fetchval('SELECT pg_has_role(current_user,$1,\'MEMBER\')', owner)
        with pytest.raises(asyncpg.RaiseError):
            async with conn.transaction():
                await conn.fetchrow(f'SELECT * FROM {schema}.fixture_admission_lock($1)', 101)
    assert not await pool.fetchval("""SELECT EXISTS(SELECT 1 FROM pg_proc p
      CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
      WHERE p.oid=$1::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE')""",
      f'{schema}.fixture_admission_lock(bigint)')
    assert not await pool.fetchval('SELECT rolcanlogin FROM pg_roles WHERE rolname=$1', owner)


async def test_revoke_first_denies_and_cannot_be_spoofed(trusted_env):
    pool, schema, (_, runtime, _), owner, runtime_pool, policy_pool = trusted_env
    await update(policy_pool, 0)
    await update(policy_pool, 1, testers=())
    before = await snapshot(pool)
    async with runtime_pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(f'SELECT * FROM {schema}.fixture_admission_lock($1)', 101)
            assert (row['policy_version'], row['admitted']) == (2, False)
        for sql in (
            'UPDATE admission_policy_shadow SET version=99',
            "INSERT INTO admission_membership_shadow VALUES(101,'admin')",
            'DELETE FROM admission_membership_shadow',
            "INSERT INTO admission_policy_audit_shadow VALUES(gen_random_uuid(),100,99,repeat('a',64),now())",
            'DELETE FROM admission_policy_audit_shadow',
            'ALTER TABLE admission_policy_shadow DISABLE TRIGGER ALL',
            f'ALTER FUNCTION {schema}.fixture_admission_lock(bigint) RENAME TO stolen',
            f'CREATE FUNCTION {schema}.fixture_fake() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$',
            f'GRANT {owner} TO {runtime}',
            f'SET ROLE {owner}',
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(sql)
            assert await snapshot(pool) == before
        # A caller-writable temp table and changed search_path cannot shadow qualified objects.
        await conn.execute('CREATE TEMP TABLE admission_policy_shadow(id int,version bigint,initialized bool)')
        await conn.execute('INSERT INTO admission_policy_shadow VALUES(1,999,true)')
        await conn.execute(f'SET search_path = pg_temp, {schema}')
        async with conn.transaction():
            row = await conn.fetchrow(f'SELECT * FROM {schema}.fixture_admission_lock($1)', 101)
            assert row['policy_version'] == 2 and not row['admitted']
        assert await snapshot(pool) == before


async def test_protected_commit_first_serializes_revocation_and_ledger(trusted_env, env):
    pool, schema, (_, runtime, _), _, runtime_pool, policy_pool = trusted_env
    _, _, service, _ = env
    tester = await service.identity(101)
    await service.accept(tester)
    await update(policy_pool, 0)
    async with pool.acquire() as owner_conn:
        await owner_conn.execute(f'GRANT SELECT,UPDATE ON {schema}.wallets TO {runtime}')
        await owner_conn.execute(f'GRANT SELECT,INSERT ON {schema}.ledger TO {runtime}')
    before = await pool.fetchval('SELECT count(*) FROM ledger')
    async with runtime_pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(f'SELECT * FROM {schema}.fixture_admission_lock($1)', 101)
        assert row['admitted'] and row['policy_version'] == 1
        await conn.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live' FOR UPDATE", tester)
        revoke = asyncio.create_task(update(policy_pool, 1, testers=()))
        await asyncio.sleep(.1)
        assert not revoke.done(), 'revoke must wait for transaction-scoped share lock'
        await service.movement(conn, tester, 'live', 'trusted-lock-fixture-credit', 'pilot_grant', 100, 0)
        await service.movement(conn, tester, 'live', 'trusted-lock-fixture-credit', 'pilot_grant', 100, 0)
    assert await asyncio.wait_for(revoke, 5) == 2
    async with runtime_pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(f'SELECT * FROM {schema}.fixture_admission_lock($1)', 101)
        assert not row['admitted']
    assert await pool.fetchval('SELECT count(*) FROM ledger') == before + 1
    assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live'", tester) == 100


async def test_replay_concurrent_updates_and_lock_timeout(trusted_env):
    pool, schema, _, _, runtime_pool, policy_pool = trusted_env
    op = uuid.uuid4()
    assert await update(policy_pool, 0, operation=op) == 1
    assert await update(policy_pool, 0, operation=op) == 1
    with pytest.raises(VersionConflict):
        await update(policy_pool, 0, testers=(), operation=op)
    async with runtime_pool.acquire() as runtime, runtime.transaction():
        await runtime.fetchrow(f'SELECT * FROM {schema}.fixture_admission_lock($1)', 101)
        async with policy_pool.acquire() as writer, writer.transaction():
            await writer.execute("SET LOCAL lock_timeout='100ms'")
            with pytest.raises(asyncpg.LockNotAvailableError):
                await writer.execute('UPDATE admission_policy_shadow SET version=version+1 WHERE id=1')
    outcomes = await asyncio.gather(update(policy_pool, 1, testers=()), update(policy_pool, 1, testers=(102,)), return_exceptions=True)
    assert sum(x == 2 for x in outcomes) == 1
    assert sum(isinstance(x, VersionConflict) for x in outcomes) == 1
