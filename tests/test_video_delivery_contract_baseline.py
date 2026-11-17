"""Expected-green, independent mock/PG checks for existing video behavior."""
import asyncio
import pytest
from elevenbot.core import Rejected
from elevenbot.video import VideoPilot
from video_delivery_helpers import TelegramMock, assert_preserved, ledger_state, seed, MP4


async def test_confirmed_send_is_recorded_and_repeated_poll_does_not_send(env):
    pool, service, user, job, api, pilot = await seed(env)
    ledger = await ledger_state(pool)
    bot = TelegramMock()
    assert await pilot.notify_one(bot)
    assert await pool.fetchval('SELECT notify_at IS NULL FROM video_jobs WHERE id=$1', job)
    assert not await VideoPilot(pool, pilot.cfg, api=api).notify_one(bot)
    assert bot.attempts == bot.accepted == 1
    await assert_preserved(pool, service, user, job, api, ledger)


async def test_concurrent_workers_do_not_send_same_inflight_job(env):
    pool, service, user, job, api, pilot = await seed(env)
    ledger = await ledger_state(pool)
    bot = TelegramMock('held')
    bot.started, bot.resume = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(pilot.notify_one(bot))
    try:
        await asyncio.wait_for(bot.started.wait(), 5)
        assert not await VideoPilot(pool, pilot.cfg, api=api).notify_one(bot)
    finally:
        bot.resume.set()
        await task
    assert bot.attempts == bot.accepted == 1
    await assert_preserved(pool, service, user, job, api, ledger)


async def test_library_reopens_same_mp4_and_denies_other_identity(env):
    pool, service, user, job, api, _ = await seed(env)
    assert (await service.video_work(user, job))['video'] == MP4
    assert (await service.video_work(user, job))['video'] == MP4
    other = await service.identity(777)
    await service.accept(other)
    ledger = await ledger_state(pool)
    with pytest.raises(Rejected):
        await service.video_work(other, job)
    await assert_preserved(pool, service, user, job, api, ledger)
