"""JO-02 checks on the existing speech queue, with disposable DB and mock provider."""
import asyncio
from dataclasses import replace

import pytest
from elevenbot.core import Rejected, Service
from elevenbot.providers import MockProvider
from elevenbot.worker import Worker


async def test_capacity_rejection_cancel_and_fifo(env):
    pool, cfg, _, first = env
    cfg = replace(cfg, queue_max_pending=2, concurrency=1)
    service = Service(pool, cfg)
    second, third = await service.identity(101), await service.identity(102)
    await service.accept(second)
    await service.accept(third)
    q1, _ = await service.quote(first, 'First', 'demo')
    q2, _ = await service.quote(second, 'Second', 'demo')
    q3, _ = await service.quote(third, 'Third', 'demo')
    j1 = await service.confirm(first, q1)
    j2 = await service.confirm(second, q2)
    before = dict(await service.wallet(third))
    with pytest.raises(Rejected, match='Очередь заполнена'):
        await service.confirm(third, q3)
    assert dict(await service.wallet(third)) == before
    assert await pool.fetchval('SELECT count(*) FROM jobs WHERE user_id=$1', third) == 0
    # Existing idempotent confirmation remains available despite saturation.
    assert await service.confirm(first, q1) == j1
    assert await service.cancel(first, j1)
    assert await service.cancel(first, j1)
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='release'", j1) == 1
    j3 = await service.confirm(third, q3)
    worker = Worker(pool, cfg, MockProvider())
    claimed = await worker.claim()
    assert claimed['id'] == j2
    assert await worker.claim() is None  # One dispatch in progress.
    with pytest.raises(Rejected, match='уже нельзя отменить'):
        await service.cancel(second, j2)
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='release'", j2) == 0
    assert (await service.owned(third, j3))['status'] == 'queued'


async def test_simultaneous_users_cannot_overfill_queue(env):
    pool, cfg, _, first = env
    service = Service(pool, replace(cfg, queue_max_pending=1))
    second = await service.identity(101)
    await service.accept(second)
    q1, _ = await service.quote(first, 'One', 'demo')
    q2, _ = await service.quote(second, 'Two', 'demo')
    results = await asyncio.gather(service.confirm(first, q1), service.confirm(second, q2), return_exceptions=True)
    assert sum(isinstance(item, Rejected) for item in results) == 1
    assert await pool.fetchval("SELECT count(*) FROM jobs WHERE status='queued'") == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='reserve'") == 1


async def test_saved_result_survives_worker_loop_shutdown(env):
    pool, cfg, service, user = env
    q, _ = await service.quote(user, 'Shutdown', 'demo')
    job = await service.confirm(user, q)
    provider = MockProvider()
    worker = Worker(pool, cfg, provider)
    assert await worker.run_one()
    row = await service.owned(user, job)
    assert row['status'] == 'succeeded'
    path = worker.storage.path(row['storage_key'])
    original = path.read_bytes()
    loop = asyncio.create_task(worker.loop())
    await asyncio.sleep(0.1)
    loop.cancel()
    with pytest.raises(asyncio.CancelledError):
        await loop
    assert (await service.owned(user, job))['status'] == 'succeeded'
    assert path.read_bytes() == original and provider.calls == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='capture'", job) == 1
