import asyncio
import hashlib
import runpy
from pathlib import Path

import httpx
import pytest
from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

from elevenbot.providers import MockProvider
from elevenbot.worker import Worker
from scripts.dev_runtime import KEY, offline_clients

fixture_module = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "dev_bot.py")
)
fixture_environment = fixture_module["fixture_environment"]


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


async def test_telegram_fixture_orders_updates_and_records_media():
    fixture = fixture_module["TelegramFixture"](None, None, 9)
    async with TestClient(TestServer(fixture.app())) as client:
        token = fixture_module["TOKEN"]
        update = await client.post("/fixture/updates", json={"chat": 101, "text": "/start"})
        assert update.status == 201 and await update.json() == {"update_id": 9}
        callback = await client.post("/fixture/updates", json={
            "chat": 101, "callback": "home", "message_id": 1000})
        assert callback.status == 201 and await callback.json() == {"update_id": 10}
        polled = await client.post(f"/bot{token}/getUpdates", data={"offset": "10"})
        event, = (await polled.json())["result"]
        assert event["update_id"] == 10 and event["callback_query"]["message"]["message_id"] == 1000
        assert (await client.post("/botwrong/getUpdates")).status == 404
        video = FormData()
        video.add_field("chat_id", "101")
        video.add_field("video", b"fixture", filename="fixture.mp4")
        assert (await client.post(f"/bot{token}/sendVideo", data=video)).status == 200
        reply, = (await (await client.get("/fixture/replies?after=0")).json())["replies"]
        assert reply["method"] == "sendvideo" and reply["chat"] == 101
        assert reply["media_sha256"] == hashlib.sha256(b"fixture").hexdigest()


async def test_offline_provider_has_no_external_fallback():
    with offline_clients():
        async with httpx.AsyncClient() as client:
            blocked = await client.get("https://outside.invalid", headers={"Authorization": f"Bearer {KEY}"})
            assert blocked.status_code == 403
            speech = await client.post("https://clodex.xyz/v1/audio/speech",
                                       headers={"Authorization": f"Bearer {KEY}"})
            assert speech.status_code == 200 and speech.headers["Content-Type"] == "audio/mpeg"


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
