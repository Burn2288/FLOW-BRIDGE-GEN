"""Disposable PostgreSQL checks for inert shadow primitives, not runtime cutover."""
import asyncio
from dataclasses import replace
import logging
import uuid
import asyncpg
import pytest

from elevenbot.admission_store import (CutoverBlocked, PolicyDenied, PolicyUnavailable,
    VersionConflict, decide_on, enable_authoritative_policy, replace_policy, require_on, shadow_compare)
from elevenbot.db import migrate


async def authorized(conn, actor):
    return actor == 100


async def forbidden(conn, actor):
    return False


async def test_shadow_unavailable_never_changes_legacy_decision(caplog):
    from elevenbot.config import Config
    class BrokenPool:
        def acquire(self):
            raise RuntimeError('sensitive-fixture-must-not-appear')
    cfg = Config(access_mode='private', admin_ids=(100,), pilot_user_ids=(101,))
    with caplog.at_level(logging.INFO, logger='elevenbot.admission_store'):
        assert await shadow_compare(BrokenPool(), cfg, 101) == (True, 'SHADOW_UNAVAILABLE')
        assert await shadow_compare(BrokenPool(), cfg, 999) == (False, 'SHADOW_UNAVAILABLE')
    assert 'sensitive-fixture-must-not-appear' not in caplog.text


async def update(pool, version, *, testers=(101,), op=None, actor=100, check=authorized):
    return await replace_policy(pool, expected_version=version, operation_id=op or uuid.uuid4(),
                                actor=actor, admins=(100,), testers=testers, authorize_admin=check)


async def test_shadow_is_inert_until_initialized_and_rerun_is_idempotent(env, caplog):
    pool, cfg, _, _ = env
    cfg = replace(cfg, access_mode='private', admin_ids=(100,), pilot_user_ids=(101,))
    async with pool.acquire() as conn, conn.transaction():
        with pytest.raises(PolicyUnavailable):
            await decide_on(conn, 101)
    with pytest.raises(CutoverBlocked):
        enable_authoritative_policy()
    assert await update(pool, 0, testers=()) == 1
    with caplog.at_level(logging.INFO, logger='elevenbot.admission_store'):
        assert await shadow_compare(pool, cfg, 101) == (True, 'MISMATCH')
    assert 'MISMATCH' in caplog.text and '101' not in caplog.text
    await migrate(pool)
    assert await pool.fetchval('SELECT version FROM admission_policy_shadow') == 1
    assert await pool.fetchval("SELECT count(*) FROM schema_migrations WHERE version='040_admission_policy_shadow.sql'") == 1


async def test_membership_roles_cas_idempotency_and_audit_immutability(env):
    pool, _, _, _ = env
    op = uuid.uuid4()
    assert await update(pool, 0, op=op) == 1
    assert await update(pool, 0, op=op) == 1
    with pytest.raises(VersionConflict):
        await update(pool, 0, testers=(), op=op)
    with pytest.raises(PolicyDenied):
        await update(pool, 1, check=forbidden)
    async with pool.acquire() as conn, conn.transaction():
        admin = await decide_on(conn, 100)
        tester = await decide_on(conn, 101)
        stranger = await decide_on(conn, 999)
        assert (admin.role, tester.role, stranger.allowed) == ('admin', 'tester', False)
    with pytest.raises(asyncpg.RaiseError):
        await pool.execute('DELETE FROM admission_policy_audit_shadow')
    assert await pool.fetchval('SELECT count(*) FROM admission_policy_audit_shadow') == 1


async def test_concurrent_updates_do_not_lose_changes(env):
    pool, _, _, _ = env
    await update(pool, 0)
    results = await asyncio.gather(update(pool, 1, testers=(102,)), update(pool, 1, testers=(103,)),
                                   return_exceptions=True)
    assert sum(isinstance(item, VersionConflict) for item in results) == 1
    assert sum(item == 2 for item in results) == 1
    assert await pool.fetchval('SELECT count(*) FROM admission_policy_audit_shadow') == 2


async def test_revoke_and_protected_transaction_lock_order(env):
    pool, _, service, user = env
    await update(pool, 0)
    tester = await service.identity(101)
    await service.accept(tester)
    previous = await pool.fetchval('SELECT count(*) FROM ledger')
    async with pool.acquire() as conn, conn.transaction():
        decision = await require_on(conn, 101)
        assert decision.version == 1
        await conn.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live' FOR UPDATE", tester)
        revoke = asyncio.create_task(update(pool, 1, testers=()))
        await asyncio.sleep(0.1)
        assert not revoke.done(), 'revocation must wait for authorized transaction'
        await service.movement(conn, tester, 'live', 'shadow-fixture-credit', 'pilot_grant', 100, 0)
    assert await asyncio.wait_for(revoke, 5) == 2
    async with pool.acquire() as conn, conn.transaction():
        with pytest.raises(PolicyDenied):
            await require_on(conn, 101)
    assert await pool.fetchval('SELECT count(*) FROM ledger') == previous + 1
    assert await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='live'", tester) == 100
    assert await pool.fetchval('SELECT EXISTS(SELECT 1 FROM users WHERE id=$1)', user)
