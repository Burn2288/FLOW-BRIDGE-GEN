"""Real worker subprocess ownership on a disposable PostgreSQL fixture."""
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from elevenbot.providers import MockProvider, UnknownOutcome
from elevenbot.worker import Worker

ROOT = Path(__file__).resolve().parents[1]


async def start_child(schema, *, hold=False):
    env = os.environ | {'FT013_SCHEMA': schema, 'FT013_HOLD': '1' if hold else '0',
                        'PYTHONPATH': os.pathsep.join((str(ROOT / 'src'), str(ROOT)))}
    process = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'verification/ft013/claim_worker.py'),
        cwd=str(ROOT), env=env, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    line = await asyncio.wait_for(process.stdout.readline(), 15)
    if line.strip() != b'READY':
        _, stderr = await process.communicate()
        match = re.search(rb'(?m)^([A-Za-z][A-Za-z0-9_.]*(?:Error|Exception))(?::|$)', stderr)
        category = match.group(1).decode('ascii') if match else 'unknown'
        pytest.fail(f'Worker fixture failed before readiness: {category}')
    return process


async def stop_child(process):
    if process.returncode is None:
        process.kill()
    await asyncio.wait_for(process.communicate(), 10)


async def queue_one(service, user):
    quote, _ = await service.quote(user, 'Fixture', 'demo')
    return await service.confirm(user, quote)


async def test_two_real_processes_claim_only_once(env):
    pool, _, service, user = env
    job = await queue_one(service, user)
    schema = await pool.fetchval('SELECT current_schema()')
    children = []
    try:
        children = await asyncio.gather(start_child(schema), start_child(schema))
        for process in children:
            process.stdin.write(b'go\n')
            await process.stdin.drain()
        results = [json.loads(await asyncio.wait_for(process.stdout.readline(), 15)) for process in children]
        assert sum(item is not None for item in results) == 1
        claimed = next(item for item in results if item is not None)
        assert claimed['id'] == str(job)
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='reserve'", job) == 1
    finally:
        for process in children:
            await stop_child(process)


async def test_killed_owner_recovery_never_reposts_or_accepts_stale_fence(env):
    pool, cfg, service, user = env
    job = await queue_one(service, user)
    schema = await pool.fetchval('SELECT current_schema()')
    process = await start_child(schema, hold=True)
    try:
        process.stdin.write(b'go\n')
        await process.stdin.drain()
        claim = json.loads(await asyncio.wait_for(process.stdout.readline(), 15))
        assert claim['id'] == str(job)
    finally:
        await stop_child(process)
    # Advance only this isolated fixture's lease; no wall-clock wait or production DB.
    await pool.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=$1", job)
    worker = Worker(pool, cfg, MockProvider())
    await worker.recover()
    assert (await service.owned(user, job))['status'] == 'uncertain'
    assert not await worker.run_one() and worker.provider.calls == 0
    assert not await service.settle(job, 'release', uuid_from(claim['fence']))
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind IN ('capture','release')", job) == 0


def uuid_from(value):
    from uuid import UUID
    return UUID(value)


async def test_old_fence_cannot_settle_simulated_new_owner(env):
    pool, cfg, service, user = env
    job = await queue_one(service, user)
    worker = Worker(pool, cfg, MockProvider())
    old = await worker.claim()
    new_fence = uuid4()
    # Synthetic ownership change tests the fence check; application does not requeue uncertain jobs.
    await pool.execute("UPDATE jobs SET fence=$2,lease_until=now()+interval '3 minutes' WHERE id=$1", job, new_fence)
    assert not await service.settle(job, 'release', old['fence'])
    assert await service.settle(job, 'release', new_fence)
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='release'", job) == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='capture'", job) == 0


async def test_unknown_provider_response_is_not_reposted(env):
    pool, cfg, service, user = env
    job = await queue_one(service, user)
    class UncertainProvider:
        calls = 0
        async def synthesize(self, *_args):
            self.calls += 1
            raise UnknownOutcome()
    provider = UncertainProvider()
    worker = Worker(pool, cfg, provider)
    assert await worker.run_one()
    assert (await service.owned(user, job))['status'] == 'uncertain'
    assert not await worker.run_one() and provider.calls == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='reserve'", job) == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind IN ('capture','release')", job) == 0
