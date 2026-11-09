"""Single-attempt CLODEX music pilot, with an isolated ledger and durable audio job."""

import asyncio
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

import httpx
from aiogram.exceptions import ClientDecodeError, TelegramAPIError
from aiogram.types import BufferedInputFile

from .anymodel_speech import validate_mp3
from .anymodel import AnyModelError
from .core import Rejected
from .interaction import trace_interaction
from .pricing import PriceUnavailable, ProviderCost, Request
from .progress import TaskProgress, UNKNOWN
from .submission import ProviderRefused, check_submission_refusal
from .video import ID_PATTERN, VideoAPI, VideoProtocolError

MODEL = 'clodex-video/music-v1'
TITLE = 'Leonardo Music'
OPERATION = 'audio.generate'
AUDIOS = '/v1/audios'
ROUTES = {'music', 'musicprompt', 'musicconfirm', 'musiccancel', 'musicwork'}
MAX_MP3 = 48 * 1024 * 1024


class MusicAPI(VideoAPI):
    @staticmethod
    def payload(prompt):
        return {'model': MODEL, 'prompt': prompt, 'n': 1}

    async def cost(self, request):
        if (request.provider, request.model, request.operation, request.params) != ('clodex', MODEL, OPERATION, {'n': 1}):
            raise PriceUnavailable()
        if not request.prompt.strip() or len(request.prompt) > 5000 or '\x00' in request.prompt:
            raise PriceUnavailable()
        try:
            body = await self.json('POST', AUDIOS+'/estimate', json=self.payload(request.prompt))
            data = body['data']
            if body.get('success') is not True or data.get('model') != MODEL:
                raise ValueError()
            price = Decimal(str(data['cost_usd']))
            if not price.is_finite() or not 0 < price <= 100:
                raise ValueError()
        except (httpx.HTTPError, TimeoutError, VideoProtocolError, KeyError, AttributeError,
                TypeError, InvalidOperation, ValueError):
            raise PriceUnavailable() from None
        return ProviderCost(price, 'USD', True, 'CLODEX /v1/audios/estimate · cost_usd', '1 трек')

    async def create(self, prompt):
        async with asyncio.timeout(25), self.client() as client:
            async with client.stream('POST', AUDIOS, json=self.payload(prompt)) as response:
                raw = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    raw.extend(chunk)
                    if len(raw) > 65_536:
                        raise VideoProtocolError('music_create_size')
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise VideoProtocolError('music_create_shape')
                data = body.get('data') if isinstance(body.get('data'), dict) else {}
                task = data.get('task_id') or data.get('id') or body.get('task_id') or body.get('id')
                if not response.is_success and not task:
                    if response.status_code in (400, 422) and body.get('code') == 'invalid_request' and body.get('data') is None:
                        raise ProviderRefused('CLODEX отклонил аудиозапрос.')
                    rejection = httpx.Response(response.status_code, content=bytes(raw))
                    await check_submission_refusal(rejection)
                response.raise_for_status()
        if not isinstance(task, str) or not ID_PATTERN.fullmatch(task):
            raise VideoProtocolError('music_task_id')
        return task

    async def status(self, task):
        body = await self.json('GET', f'{AUDIOS}/{task}')
        data = body.get('data') if isinstance(body.get('data'), dict) else body
        status = str(data.get('status', '')).lower()
        if status in ('done', 'completed', 'succeeded', 'success'):
            return 'ready'
        if status in ('failed', 'error', 'cancelled', 'canceled'):
            return 'failed'
        return 'polling'

    async def download(self, task):
        raw = bytearray()
        async with asyncio.timeout(60), self.client() as client:
            async with client.stream('GET', f'{AUDIOS}/{task}/content', params={'index': 0}) as response:
                response.raise_for_status()
                media = response.headers.get('content-type', '').split(';', 1)[0].lower()
                if media not in ('audio/mpeg', 'audio/mp3', 'application/octet-stream'):
                    raise VideoProtocolError('music_media')
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_MP3:
                        raise VideoProtocolError('music_size')
        audio = bytes(raw)
        await asyncio.to_thread(validate_mp3, audio)
        return audio


def request(prompt):
    return Request('clodex', MODEL, OPERATION, TITLE, prompt, {'n': 1})


class MusicPilot:
    def __init__(self, pool, cfg, *, api=None):
        self.pool, self.cfg = pool, cfg
        self.api = api or MusicAPI(cfg.clodex_key)

    def owner(self, chat):
        return self.cfg.access_mode == 'private' and not self.cfg.payments_enabled and (
            chat > 0 and chat == self.cfg.clodex_music_owner and chat in self.cfg.admin_ids
        )

    async def balance(self, user, conn=None):
        return await (conn or self.pool).fetchrow("""
            SELECT coalesce(sum(da),0)::bigint AS available,coalesce(sum(dr),0)::bigint AS reserved
            FROM clodex_music_ledger WHERE user_id=$1
            """, user)

    async def grant(self, user, chat, quote_id):
        if not self.owner(chat):
            raise Rejected('Пилот недоступен.')
        async with self.pool.acquire() as conn, conn.transaction():
            amount = await conn.fetchval("""
                SELECT (q.price->>'total')::bigint FROM task_price_quotes q
                JOIN identities i ON i.user_id=q.user_id AND i.platform='telegram'
                WHERE q.id=$1 AND q.user_id=$2 AND i.external_id=$3 AND i.terms_version='1'
                  AND i.accepted_at IS NOT NULL AND q.state='pending' AND q.expires_at>now()
                  AND q.provider='clodex' AND q.model_id=$4 AND q.operation=$5
                """, quote_id, user, chat, MODEL, OPERATION)
            if not amount or amount < 0:
                raise Rejected('Нужна свежая положительная оценка пилота.')
            return await conn.fetchval("""
                INSERT INTO clodex_music_ledger VALUES($1,$2,'credit',$3,0)
                ON CONFLICT DO NOTHING RETURNING da
                """, user, quote_id, amount)

    async def confirm(self, pricing, user, chat, quote_id, update_id, session):
        async def validate(conn, req):
            if not self.owner(chat) or not session() or not self.cfg.clodex_music_live:
                raise Rejected('Пилот закрыт. Войдите через /admin.')
            if (req.provider, req.model, req.operation, req.params) != ('clodex', MODEL, OPERATION, {'n': 1}):
                raise Rejected('Оценка недоступна.')
            if await conn.fetchval('SELECT EXISTS(SELECT 1 FROM clodex_music_jobs WHERE user_id=$1)',user):
                raise Rejected('Единственная попытка уже использована.')

        async def prepare(conn, quote):
            await pricing.admin(conn, user, chat)
            amount = int(quote.price['total'])
            funds = await self.balance(user,conn)
            if amount<=0 or funds['available'] < amount:
                raise Rejected('Недостаточно тестовых токенов для Leonardo Music.')
            await conn.execute("""
                INSERT INTO clodex_music_jobs(id,user_id,chat_id,status) VALUES($1,$2,$3,'queued')
                """, quote.id,user,chat)
            await conn.execute("""
                INSERT INTO clodex_music_ledger VALUES($1,$2,'reserve',-$3::bigint,$3)
                """, user,quote.id,amount)

        return await pricing.confirm(user,quote_id,update_id,prepare,validate=validate,track_interaction=False)

    async def work(self, user, job):
        row=await self.pool.fetchrow("""
            SELECT mp3 FROM clodex_music_jobs WHERE id=$1 AND user_id=$2 AND mp3 IS NOT NULL AND expires_at>now()
            """,job,user)
        if not row:
            raise Rejected('Трек недоступен или срок хранения истёк.')
        return row['mp3']

    async def settle(self, job, status, audio=None):
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("""
                UPDATE clodex_music_jobs SET status=$2,mp3=$3,next_at=now(),last_error=NULL WHERE id=$1
                """,job,status,audio)
            await conn.execute("""
                INSERT INTO clodex_music_ledger
                SELECT user_id,quote_id,$2,CASE WHEN $2='release' THEN dr ELSE 0 END,-dr
                FROM clodex_music_ledger WHERE quote_id=$1 AND kind='reserve'
                ON CONFLICT DO NOTHING
                """,job,'capture' if audio is not None else 'release')

    async def send(self, bot, chat, audio):
        await bot.send_audio(chat, BufferedInputFile(audio,filename='leonardo-music.mp3'),
                             title=TITLE, caption=f'{TITLE} · CLODEX')

    async def tick(self, bot):
        row=await self.pool.fetchrow("""
            UPDATE clodex_music_jobs j SET next_at=now()+interval '2 minutes',
                status=CASE j.status WHEN 'queued' THEN 'submitting' WHEN 'ready' THEN 'delivering' ELSE j.status END
            FROM (
                SELECT m.id,m.status FROM clodex_music_jobs m
                JOIN identities i ON i.user_id=m.user_id AND i.platform='telegram' AND i.external_id=m.chat_id
                WHERE m.next_at<=now() AND m.status IN ('queued','submitting','polling','ready','delivering')
                ORDER BY m.next_at LIMIT 1 FOR UPDATE OF m SKIP LOCKED
            ) due,task_price_quotes q
            WHERE j.id=due.id AND q.id=j.id
            RETURNING j.*,due.status AS previous,q.request->>'prompt' AS prompt
            """)
        if not row:
            return False
        progress=TaskProgress(bot,self.pool)
        job,chat,message,previous=row['id'],row['chat_id'],row['status_message_id'],row['previous']
        if previous=='queued':
            message=await progress.start(chat,TITLE,OPERATION)
            await self.pool.execute('UPDATE clodex_music_jobs SET status_message_id=$2 WHERE id=$1',job,message)
            try:
                task=await self.api.create(row['prompt'])
            except ProviderRefused:
                await self.settle(job,'failed')
                await progress.finish(chat,message,TITLE,'CLODEX отклонил запрос. Резерв возвращён.')
            except (httpx.HTTPError,TimeoutError,VideoProtocolError,ValueError) as error:
                await self.unknown(progress,row,message,'create_'+type(error).__name__)
            else:
                await self.pool.execute("""
                    UPDATE clodex_music_jobs SET provider_id=$2,status='polling',next_at=now() WHERE id=$1
                    """,job,task)
        elif previous=='submitting':
            await self.unknown(progress,row,message,'create_interrupted')
        elif previous=='polling':
            if row['expires_at']<=datetime.now(timezone.utc):
                await self.unknown(progress,row,message,'poll_expired')
                return True
            stage='poll'
            try:
                status=await self.api.status(row['provider_id'])
                if status=='ready':
                    stage='download'
                    audio=await self.api.download(row['provider_id'])
                    await self.settle(job,'ready',audio)
                elif status=='failed':
                    await self.settle(job,'failed')
                    await progress.finish(chat,message,TITLE,'CLODEX сообщил об ошибке. Резерв возвращён.')
                else:
                    await self.reschedule(job)
            except (httpx.HTTPError,TimeoutError,VideoProtocolError,ValueError,AnyModelError) as error:
                detail=str(error) if isinstance(error,VideoProtocolError) else type(error).__name__
                await self.reschedule(job,stage+'_'+detail)
        else:
            delivered=False
            if previous=='ready':
                try:
                    async with asyncio.timeout(60):
                        await self.send(bot,chat,row['mp3'])
                except (TelegramAPIError,ClientDecodeError,TimeoutError):
                    pass
                else:
                    delivered=True
            await self.pool.execute('UPDATE clodex_music_jobs SET status=$2 WHERE id=$1',
                                    job,'delivered' if delivered else 'delivery_unknown')
            await progress.finish(chat,message,TITLE,'Готово.' if delivered else
                'Трек сохранён в «Моих работах». Доставка не подтверждена.',success=delivered)
        return True

    async def reschedule(self, job, code=None):
        await self.pool.execute("""
            UPDATE clodex_music_jobs SET next_at=now()+interval '5 seconds',last_error=$2 WHERE id=$1
            """,job,code)

    async def unknown(self, progress, row, message, code):
        await self.pool.execute("UPDATE clodex_music_jobs SET status='unknown',last_error=$2 WHERE id=$1",row['id'],code)
        await progress.finish(row['chat_id'],message,TITLE,UNKNOWN+' Резерв на сверке.')

    async def loop(self, bot):
        while True:
            try:
                if await self.tick(bot):
                    continue
            except Exception as error:
                trace_interaction('clodex-music','music_worker_error',error_type=type(error).__name__)
            await asyncio.sleep(2)
