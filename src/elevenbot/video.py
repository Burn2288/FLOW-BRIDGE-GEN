"""Private Veo pilot. A confirmed quote can dispatch at most one create request."""

import asyncio
from decimal import Decimal, InvalidOperation
import json
import re
import time
from uuid import uuid4

import httpx

from .core import Rejected, Service, uid
from .interaction import trace_interaction

MODES = {
    'standard': ('clodex-video/veo-3.1', 'Обычный', '🎬 Генерировать видео'),
    'fast': ('clodex-video/veo-3.1-fast', 'Fast', '⚡ Режим: Fast'),
}
ROOT = 'https://clodex.xyz'
VIDEOS = '/v1/videos'
MAX_VIDEO_BYTES = 49_000_000
ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,180}')

def video_status_detail(body):
    stage = body.get('status')
    if stage == 'in_progress':
        stage = 'processing'
    percent = body.get('progress')
    return stage, percent if type(percent) is int and 0<=percent<=100 else None


class VideoProtocolError(Exception):
    pass


class InvalidVideoError(VideoProtocolError):
    pass


def video_modes(cfg, snapshot, external_id):
    if not cfg.video_pilot or external_id not in cfg.admin_ids or cfg.access_mode != 'private':
        return {}
    if snapshot['fresh_until'] <= time.time():
        return {}
    ids = {
        m['id'] for m in snapshot['models']
        if m.get('provider') == 'clodex' and m.get('availability') == 'key_available'
        and 'openai-video' in m.get('protocols', [])
    }
    return {mode: details for mode, details in MODES.items() if details[0] in ids}


def payload(model, prompt):
    return {'model': model, 'prompt': prompt, 'duration': 4, 'resolution': '720p', 'aspect_ratio': '16:9'}


class VideoAPI:
    def __init__(self, key, *, transport=None):
        self.key, self.transport = key, transport

    def client(self):
        return httpx.AsyncClient(base_url=ROOT, headers={'Authorization': 'Bearer '+self.key},
                                 timeout=20, follow_redirects=False, trust_env=False, transport=self.transport)

    async def json(self, method, path, **kwargs):
        async with asyncio.timeout(25), self.client() as client:
            async with client.stream(method, path, **kwargs) as response:
                response.raise_for_status()
                raw = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    raw.extend(chunk)
                    if len(raw) > 65_536:
                        raise VideoProtocolError('json_size')
        try:
            result = json.loads(raw)
        except ValueError:
            raise VideoProtocolError('json_body') from None
        if not isinstance(result, dict):
            raise VideoProtocolError('json_shape')
        return result

    async def estimate(self, model, prompt):
        body = await self.json('POST', VIDEOS+'/estimate', json=payload(model, prompt))
        data = body.get('data')
        if body.get('success') is not True or not isinstance(data, dict) or data.get('model') != model:
            raise VideoProtocolError('quote_shape')
        try:
            price = Decimal(str(data.get('cost_usd')))
        except InvalidOperation:
            raise VideoProtocolError('quote_amount') from None
        if not price.is_finite() or not 0 <= price <= 10000:
            raise VideoProtocolError('quote_amount')
        return price

    async def create(self, model, prompt):
        body = await self.json('POST', VIDEOS, json=payload(model, prompt))
        task = body.get('id') or body.get('request_id')
        if not isinstance(task, str) or not ID_PATTERN.fullmatch(task):
            raise VideoProtocolError('create_id')
        return task

    async def status(self, task):
        body = await self.json('GET', f'{VIDEOS}/{task}')
        status = body.get('status')
        if status in ('pending', 'queued', 'processing', 'in_progress'):
            return video_status_detail(body)
        if status in ('done', 'completed', 'succeeded'):
            return 'done'
        if status == 'failed':
            return 'failed'
        raise VideoProtocolError('status_shape')

    async def download(self, task):
        async with asyncio.timeout(40), self.client() as client:
            async with client.stream('GET', f'{VIDEOS}/{task}/content') as response:
                if response.is_redirect:
                    raise VideoProtocolError('content_redirect')
                response.raise_for_status()
                media_type = response.headers.get('content-type', '').split(';')[0].lower()
                if media_type not in ('video/mp4', 'application/octet-stream'):
                    raise VideoProtocolError('content_type')
                video = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    if len(video) + len(chunk) > MAX_VIDEO_BYTES:
                        raise VideoProtocolError('content_size')
                    video.extend(chunk)
        if len(video) < 12 or video[4:8] != b'ftyp':
            raise VideoProtocolError('content_mp4')
        return bytes(video)


def video_failure(job, stage, error):
    fields = {'error_type': type(error).__name__}
    if isinstance(error, VideoProtocolError):
        fields['reason'] = str(error)
    if isinstance(error, httpx.HTTPStatusError):
        fields['status'] = error.response.status_code
    trace_interaction(str(job), stage, operation='video', **fields)


class VideoPilot:
    provider='clodex'
    label='CLODEX'
    title='Veo 3.1'
    key_fingerprint=None

    def __init__(self, pool, cfg, *, api=None):
        self.pool, self.cfg = pool, cfg
        self.svc = Service(pool, cfg)
        self.api = api or VideoAPI(cfg.clodex_key)

    def enabled(self):
        return self.cfg.video_pilot and self.cfg.access_mode=='private' and self.cfg.interaction_mode=='live'

    async def current_price(self,model):
        return None

    async def create_task(self,model,prompt,idempotency_key):
        return await self.api.create(model,prompt),None

    async def task_status(self,task,connection):
        return await self.api.status(task)

    async def task_content(self,task,connection):
        return await self.api.download(task)

    async def quote(self, user, model, text):
        prompt = text.strip()
        if not 1 <= len(prompt) <= 4000 or '\x00' in prompt:
            raise Rejected('Отправьте текст от 1 до 4000 символов.')
        try:
            price = await self.api.estimate(model, prompt)
        except (httpx.HTTPError, TimeoutError, VideoProtocolError) as error:
            video_failure(None, 'video_estimate_failed', error)
            raise Rejected(f'{self.label}: не удалось подтвердить стоимость. Запуск закрыт.') from None
        quote_id = uuid4()
        async with self.pool.acquire() as conn:
            await self.svc.authorize(conn, user)
            await conn.execute('''
                INSERT INTO video_jobs(id,user_id,model_id,prompt,cost_usd,provider,key_fingerprint)
                VALUES($1,$2,$3,$4,$5,$6,$7)
                ''',quote_id,user,model,prompt,price,self.provider,self.key_fingerprint)
        return quote_id, price

    async def confirm(self, user, quote_id, update_id, model, *, on_accepted=None):
        if not self.enabled():
            raise Rejected('Пилот видео недоступен.')
        job = uid(quote_id)
        try:
            price=await self.current_price(model)
        except (httpx.HTTPError,TimeoutError,VideoProtocolError) as error:
            video_failure(job,'video_estimate_failed',error)
            raise Rejected(f'{self.label}: не удалось подтвердить стоимость. Запуск закрыт.') from None
        async with self.pool.acquire() as conn, conn.transaction():
            await self.svc.authorize(conn, user)
            reserved = await conn.fetchrow("""
                UPDATE video_jobs SET status='submitting',next_poll_at=now()+interval '1 minute',
                    idempotency_key=CASE WHEN provider='anymodel' THEN gen_random_uuid() ELSE idempotency_key END
                WHERE id=$1 AND user_id=$2 AND model_id=$3 AND provider=$4
                    AND key_fingerprint IS NOT DISTINCT FROM $5::text
                    AND ($6::numeric IS NULL OR cost_usd=$6)
                    AND status='quoted' AND quote_expires_at>now()
                RETURNING prompt,idempotency_key
                """,job,user,model,self.provider,self.key_fingerprint,price)
            if reserved is None:
                raise Rejected('Оценка устарела или заказ уже принят.')
            if not await self.svc.reserve_interaction_on(conn, user, update_id, unlimited=False):
                raise Rejected('Запрос уже был принят. Автоматический повтор отключён.')
        # Claim is durable before the only POST. A lost response never triggers a retry.
        if on_accepted:
            await on_accepted(job)
        try:
            provider_id,connection=await self.create_task(model,reserved["prompt"],reserved["idempotency_key"])
            await self.pool.execute("""
                UPDATE video_jobs SET status='polling',provider_id=$2,connection_id=$3,next_poll_at=now()
                WHERE id=$1 AND status='submitting'
                """, job, provider_id,connection)
        except (httpx.HTTPError, TimeoutError, VideoProtocolError) as error:
            await self.pool.execute("UPDATE video_jobs SET status='uncertain',expires_at=now()+interval '7 days' WHERE id=$1 AND status='submitting'", job)
            video_failure(job, 'video_create_uncertain', error)
            raise Rejected('Статус запуска неизвестен. Автоповтора нет.') from None

    async def poll_one(self, bot):
        # Only a short lease is written before I/O, so restarts resume by provider ID.
        row = await self.pool.fetchrow("""
            UPDATE video_jobs j SET next_poll_at=now()+interval '2 minutes'
            FROM (
                SELECT id FROM video_jobs WHERE status='polling' AND next_poll_at<=now()
                    AND provider=$1 AND key_fingerprint IS NOT DISTINCT FROM $2::text
                ORDER BY next_poll_at FOR UPDATE SKIP LOCKED LIMIT 1
            ) due
            WHERE j.id=due.id
            RETURNING j.id,j.provider_id,j.connection_id,j.next_poll_at
            """,self.provider,self.key_fingerprint)
        if not row:
            return False
        job, task, connection, lease = row
        status, video = 'polling', None
        stage = percent = None
        try:
            current = await self.task_status(task,connection)
            if isinstance(current,tuple):
                stage,percent=current
            if current == 'failed':
                status = 'failed'
            if current == 'done':
                video = await self.task_content(task,connection)
                status = 'succeeded'
        except (httpx.HTTPError, TimeoutError, VideoProtocolError) as error:
            video_failure(job, 'video_poll_failed', error)
            if isinstance(error,InvalidVideoError):
                status='failed'
        saved = await self.pool.fetchval("""
            UPDATE video_jobs SET status=$3,video=$4,
                next_poll_at=now()+interval '10 seconds',
                expires_at=CASE WHEN $3 IN ('succeeded','failed') THEN now()+interval '7 days' END,
                notify_at=CASE WHEN $3 IN ('succeeded','failed') THEN now() END,
                provider_stage=COALESCE($5,provider_stage),provider_progress=COALESCE($6,provider_progress)
            WHERE id=$1 AND next_poll_at=$2 RETURNING id
            """, job, lease, status, video, stage, percent)
        if saved and status in ('succeeded', 'failed'):
            await self.notify_one(bot)
        return True

    async def notify_one(self, bot):
        from aiogram.exceptions import TelegramAPIError
        from aiogram.types import BufferedInputFile

        row = await self.pool.fetchrow("""
            UPDATE video_jobs j SET notify_at=now()+interval '2 minutes',notify_attempts=j.notify_attempts+1
            FROM (
                SELECT id FROM video_jobs WHERE provider=$1 AND notify_at<=now() AND notify_attempts<3 AND expires_at>now()
                ORDER BY notify_at FOR UPDATE SKIP LOCKED LIMIT 1
            ) due
            WHERE j.id=due.id
            RETURNING j.id,j.user_id,j.video,j.notify_at
            """,self.provider)
        if not row:
            return False
        job, user, video, lease = row
        external = await self.pool.fetchval("""
            SELECT i.external_id FROM identities i JOIN users u ON u.id=i.user_id
            WHERE i.user_id=$1 AND i.platform='telegram' AND i.accepted_at IS NOT NULL AND NOT u.blocked
            """, user)
        if external is not None:
            try:
                async with asyncio.timeout(60):
                    if video is None:
                        await bot.send_message(external, f'{self.label}: не удалось завершить обработку видео.')
                    else:
                        await bot.send_video(external, BufferedInputFile(video, filename='grok.mp4' if self.provider=='anymodel' else 'veo.mp4'),
                                             caption=f'{self.title} · Видео также доступно в «Моих работах».')
            except (TelegramAPIError, TimeoutError) as error:
                video_failure(job, 'video_delivery_failed', error)
                return True
        await self.pool.execute('UPDATE video_jobs SET notify_at=NULL WHERE id=$1 AND notify_at=$2', job, lease)
        return True

    async def loop(self, bot):
        while True:
            try:
                await self.pool.execute("""
                    UPDATE video_jobs SET status='uncertain',expires_at=now()+interval '7 days'
                    WHERE provider=$1 AND ((status='submitting' AND next_poll_at<=now())
                       OR (provider='clodex' AND status='polling' AND created_at<now()-interval '1 day'))
                    """,self.provider)
                if await self.poll_one(bot):
                    continue
                if await self.notify_one(bot):
                    continue
            except Exception as error:
                video_failure(None, 'video_worker_failed', error)
            await asyncio.sleep(2)
