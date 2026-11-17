"""Executable acceptance cases: intentionally fail on unfixed video.py, no xfail."""
import asyncio
import pytest
from elevenbot.video import VideoPilot
from video_delivery_helpers import TelegramMock, assert_preserved, ledger_state, seed


@pytest.mark.parametrize('mode', ['accepted_then_lost', 'timeout', 'telegram_error'])
async def test_ambiguous_video_must_not_be_resent_after_restart(env, mode):
    pool, service, user, job, api, pilot = await seed(env)
    ledger = await ledger_state(pool)
    bot = TelegramMock(mode)
    assert await pilot.notify_one(bot)
    await assert_preserved(pool, service, user, job, api, ledger)
    # Advance the persisted retry due time, not a provider or Telegram clock.
    await pool.execute("UPDATE video_jobs SET notify_at=now()-interval '1 second' WHERE id=$1 AND notify_at IS NOT NULL", job)
    await VideoPilot(pool, pilot.cfg, api=api).notify_one(bot)
    await assert_preserved(pool, service, user, job, api, ledger)
    print(f'DIAGNOSTIC mode={mode} telegram_attempts={bot.attempts} accepted={bot.accepted} provider_posts=0 ledger_unchanged=true', flush=True)
    assert bot.attempts == 1, 'ambiguous Telegram outcome must never trigger automatic resend'


async def test_crash_after_claim_must_not_resend(env):
    pool, service, user, job, api, pilot = await seed(env)
    ledger = await ledger_state(pool)
    bot = TelegramMock('held')
    bot.started, bot.resume = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(pilot.notify_one(bot))
    await asyncio.wait_for(bot.started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await pool.execute("UPDATE video_jobs SET notify_at=now()-interval '1 second' WHERE id=$1 AND notify_at IS NOT NULL", job)
    bot.resume.set()
    await VideoPilot(pool, pilot.cfg, api=api).notify_one(bot)
    await assert_preserved(pool, service, user, job, api, ledger)
    print(f'DIAGNOSTIC crash_after_claim telegram_attempts={bot.attempts} provider_posts=0 ledger_unchanged=true', flush=True)
    assert bot.attempts == 1, 'unknown in-flight delivery must not be retried after restart'


async def test_ambiguous_failure_notice_must_not_be_resent(env):
    pool, _, _, job, api, pilot = await seed(env, failed=True)
    ledger = await ledger_state(pool)
    bot = TelegramMock()
    assert await pilot.notify_one(bot)
    await pool.execute("UPDATE video_jobs SET notify_at=now()-interval '1 second' WHERE id=$1 AND notify_at IS NOT NULL", job)
    await VideoPilot(pool, pilot.cfg, api=api).notify_one(bot)
    assert await ledger_state(pool) == ledger
    api.create.assert_not_awaited()
    print(f'DIAGNOSTIC failed_notice telegram_attempts={bot.attempts} accepted={bot.accepted} provider_posts=0 ledger_unchanged=true', flush=True)
    assert bot.attempts == 1, 'ambiguous failure notice must not be resent automatically'
