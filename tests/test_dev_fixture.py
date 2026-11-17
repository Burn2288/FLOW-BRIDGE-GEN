import asyncio
import runpy
from pathlib import Path

import pytest

from elevenbot.providers import MockProvider
from elevenbot.worker import Worker

fixture_environment = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "dev_bot.py")
)["fixture_environment"]


def test_dev_environment_is_fixture_only(monkeypatch):
    url = "postgresql://postgres:isolated-test-only@127.0.0.1:5432/flowbridge_dev"
    monkeypatch.setenv("DATABASE_URL", url)
    for key in ("CLODEX_API_KEY", "FAL_KEY", "ANYMODEL_API_KEY", "PLATEGA_SECRET",
                "DATABASE_MIGRATION_URL", "ADMIN_PASSWORD"):
        monkeypatch.setenv(key, "test-marker")
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    env = fixture_environment()
    assert "test-marker" not in env.values()
    assert (env["GENERATION_ENABLED"], env["PAYMENTS_ENABLED"], env["PROVIDER_MODE"]) == (
        "true", "false", "mock")
    for invalid in (url.replace("127.0.0.1", "db"), url.replace("flowbridge_dev", "elevenbot"),
                    url + "?host=remote", url.replace("isolated-test-only", "other")):
        monkeypatch.setenv("DATABASE_URL", invalid)
        with pytest.raises(SystemExit):
            fixture_environment()


async def test_two_users_make_progress_with_two_workers(env):
    pool, cfg, service, first = env
    second = await service.identity(101)
    await service.accept(second)
    both_started = asyncio.Event()

    class ConcurrentMock(MockProvider):
        arrivals = 0

        async def synthesize(self, text, voice, speed):
            self.arrivals += 1
            if self.arrivals == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 5)
            return await super().synthesize(text, voice, speed)

    async def submit(user):
        quote, _ = await service.quote(user, "Dev", "demo")
        return await service.confirm(user, quote)

    jobs = await asyncio.gather(submit(first), submit(second))
    provider = ConcurrentMock()
    workers = [Worker(pool, cfg, provider) for _ in jobs]
    assert all(await asyncio.gather(*(worker.run_one() for worker in workers)))
    for user, job in zip((first, second), jobs, strict=True):
        row = await service.owned(user, job)
        assert (row["status"], row["settlement"]) == ("succeeded", "capture")
        assert (cfg.storage / row["storage_key"]).is_file()
    assert provider.calls == 2
