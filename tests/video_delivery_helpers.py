"""Synthetic saved jobs and mock Telegram; never invokes a provider or Telegram."""
import hashlib
import uuid
from unittest.mock import AsyncMock
from elevenbot.video import VideoPilot

MP4 = b'\x00\x00\x00\x18ftypmp42synthetic-video-for-contract-test'


async def seed(env, *, failed=False):
    pool, cfg, service, user = env
    job = uuid.uuid4()
    await pool.execute("""INSERT INTO video_jobs
        (id,user_id,model_id,prompt,cost_usd,status,provider_id,video,notify_at,expires_at)
        VALUES($1,$2,'fixture-model','fixture',0,$3,$4,$5,now(),now()+interval '1 day')""",
        job, user, 'failed' if failed else 'succeeded', 'fixture-'+job.hex,
        None if failed else MP4)
    api = AsyncMock()
    return pool, service, user, job, api, VideoPilot(pool, cfg, api=api)


async def ledger_state(pool):
    rows = await pool.fetch('SELECT event_key,kind,da,dr FROM ledger ORDER BY event_key')
    return [tuple(row.values()) for row in rows]


async def assert_preserved(pool, service, user, job, api, ledger):
    assert await ledger_state(pool) == ledger
    assert hashlib.sha256((await service.video_work(user, job))['video']).digest() == hashlib.sha256(MP4).digest()
    api.create.assert_not_awaited()


class TelegramMock:
    def __init__(self, mode='ok'):
        self.mode = mode
        self.attempts = 0
        self.accepted = 0
        self.started = None
        self.resume = None

    async def send_video(self, chat, media, **kwargs):
        self.attempts += 1
        if self.mode == 'held':
            self.started.set()
            await self.resume.wait()
        if self.mode in ('accepted_then_lost', 'telegram_error', 'ok', 'held'):
            self.accepted += 1
        if self.mode in ('accepted_then_lost', 'timeout'):
            raise TimeoutError('fixture-response-lost')
        if self.mode == 'telegram_error':
            from aiogram.exceptions import TelegramAPIError
            raise TelegramAPIError(method=None, message='fixture-ambiguous')
        return type('Message', (), {'message_id': 1})()

    async def send_message(self, chat, text):
        self.attempts += 1
        self.accepted += 1
        raise TimeoutError('fixture-response-lost')
