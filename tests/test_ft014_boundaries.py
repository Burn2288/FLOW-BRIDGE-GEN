"""Cross-boundary regression on existing jobs; no live provider or payment."""
import hashlib

from elevenbot.providers import MockProvider
from elevenbot.worker import Worker


async def test_repeated_confirmation_preserves_saved_result_and_single_capture(env):
    pool, cfg, service, user = env
    quote, _ = await service.quote(user, 'Boundaries', 'demo')
    job = await service.confirm(user, quote)
    assert await service.confirm(user, quote) == job
    provider = MockProvider()
    worker = Worker(pool, cfg, provider)
    assert await worker.run_one()
    row = await service.owned(user, job)
    assert row['status'] == 'succeeded'
    path = worker.storage.path(row['storage_key'])
    digest = hashlib.sha256(path.read_bytes()).digest()
    assert await service.confirm(user, quote) == job
    assert hashlib.sha256(path.read_bytes()).digest() == digest
    assert provider.calls == 1
    for kind in ('reserve', 'capture'):
        assert await pool.fetchval('SELECT count(*) FROM ledger WHERE job_id=$1 AND kind=$2', job, kind) == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='release'", job) == 0


async def test_repeated_cancellation_has_one_release_and_no_provider_call(env):
    pool, cfg, service, user = env
    quote, _ = await service.quote(user, 'Cancel', 'demo')
    job = await service.confirm(user, quote)
    assert await service.cancel(user, job)
    assert await service.cancel(user, job)
    provider = MockProvider()
    assert not await Worker(pool, cfg, provider).run_one()
    assert provider.calls == 0
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='release'", job) == 1
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE job_id=$1 AND kind='capture'", job) == 0
