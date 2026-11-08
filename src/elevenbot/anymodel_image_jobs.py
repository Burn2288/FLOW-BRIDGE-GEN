"""Durable background image jobs for the AnyModel pilot."""

import asyncio

from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile

from .anymodel import AnyModelError, AnyModelProvider, FIBO_MODEL
from .core import Rejected, Service
from .interaction import trace_interaction

RETRYABLE_POLL = {'connect_error','connect_timeout','response_timeout','transport_error',
                  'http_429','http_502','http_504'}


class AnyModelImageJobs:
    def __init__(self,pool,cfg,*,adapter=None):
        self.pool=pool
        self.svc=Service(pool,cfg)
        self.adapter=adapter or AnyModelProvider(cfg.anymodel_key)

    async def submit(self,user,update_id,prompt,*,on_accepted=None):
        async with self.pool.acquire() as conn,conn.transaction():
            await self.svc.authorize(conn,user)
            existing=await conn.fetchval('SELECT status FROM anymodel_image_jobs WHERE update_id=$1',update_id)
            if existing or not await self.svc.reserve_interaction_on(conn,user,update_id,unlimited=False):
                raise Rejected('AnyModel: запрос уже был принят. Автоповтора нет.')
            await conn.execute("""
                INSERT INTO anymodel_image_jobs(update_id,user_id,prompt,status,next_at)
                VALUES($1,$2,$3,'submitting',now()+interval '1 minute')
                """,update_id,user,prompt)

        if on_accepted:
            await on_accepted(update_id)
        reply=None
        try:
            reply=await self.adapter.submit_image(FIBO_MODEL,prompt)
            trace_interaction(update_id,'anymodel_image_submit_response',status=reply.status)
            if reply.status==202:
                job_id=self.adapter.accepted_image_id(reply)
                await self.pool.execute("""
                    UPDATE anymodel_image_jobs SET provider_id=$2,status='pending',
                        next_at=now()+$3*interval '1 second'
                    WHERE update_id=$1 AND status='submitting'
                    """,update_id,job_id,reply.retry_after)
            else:
                result=await self.adapter.image_result(reply,update_id)
                await self.save(update_id,user,prompt,result)
        except AnyModelError as error:
            status=reply.status if reply else error.status
            unknown=status in (None,202)
            await self.pool.execute("UPDATE anymodel_image_jobs SET status=$2 WHERE update_id=$1 AND status='submitting'",
                                    update_id,'unknown' if unknown else 'failed')
            trace_interaction(update_id,'anymodel_image_submit_failed',code=error.code,status=status)
            message='исход запуска неизвестен' if unknown else str(error)
            raise Rejected(f'AnyModel: {message}. Автоповтора нет.') from None

    async def save(self,update_id,user,prompt,result,lease=None):
        async with self.pool.acquire() as conn,conn.transaction():
            active=await conn.fetchval("""
                SELECT true FROM anymodel_image_jobs WHERE update_id=$1
                AND (($2::timestamptz IS NULL AND status='submitting') OR (status='pending' AND next_at=$2))
                FOR UPDATE
                """,update_id,lease)
            if active:
                await self.svc.save_image_work_on(conn,user,update_id,FIBO_MODEL,prompt,result)
                await conn.execute("UPDATE anymodel_image_jobs SET status='ready',next_at=now() WHERE update_id=$1",update_id)

    async def poll_one(self,bot):
        row=await self.pool.fetchrow("""
            UPDATE anymodel_image_jobs j SET next_at=now()+interval '2 minutes'
            FROM (
                SELECT update_id FROM anymodel_image_jobs WHERE next_at<=now() AND expires_at>now()
                AND (status='pending' OR (status='ready' AND notify_attempts<3))
                ORDER BY next_at FOR UPDATE SKIP LOCKED LIMIT 1
            ) due WHERE j.update_id=due.update_id
            RETURNING j.update_id,j.user_id,j.prompt,j.provider_id,j.status,j.next_at
            """)
        if not row:
            return False
        update_id,user,prompt,job_id,status,lease=row
        if status=='ready':
            await self.notify(bot,update_id,user,lease)
            return True
        try:
            reply=await self.adapter.poll_image(job_id)
            if reply.status==202:
                await self.reschedule(update_id,lease,reply.retry_after)
            else:
                trace_interaction(update_id,'anymodel_image_poll_response',status=reply.status)
                result=await self.adapter.image_result(reply,update_id)
                await self.save(update_id,user,prompt,result,lease)
        except (AnyModelError,Rejected) as error:
            code=error.code if isinstance(error,AnyModelError) else 'access'
            trace_interaction(update_id,'anymodel_image_poll_failed',code=code,
                              status=error.status if isinstance(error,AnyModelError) else None)
            if code in RETRYABLE_POLL:
                await self.reschedule(update_id,lease,max(5,error.retry_after))
            else:
                await self.pool.execute("UPDATE anymodel_image_jobs SET status='failed' WHERE update_id=$1 AND next_at=$2",
                                        update_id,lease)
        return True

    async def reschedule(self,update_id,lease,delay):
        await self.pool.execute("""
            UPDATE anymodel_image_jobs SET next_at=now()+$3*interval '1 second'
            WHERE update_id=$1 AND next_at=$2
            """,update_id,lease,max(1,delay))

    async def notify(self,bot,update_id,user,lease):
        work=await self.pool.fetchrow("""
            SELECT w.image,w.filename,i.external_id
            FROM image_works w JOIN identities i ON i.user_id=w.user_id AND i.platform='telegram'
            JOIN users u ON u.id=w.user_id AND NOT u.blocked
            WHERE w.update_id=$1 AND w.user_id=$2 AND w.expires_at>now() AND i.accepted_at IS NOT NULL
            """,update_id,user)
        if work:
            await self.pool.execute("UPDATE anymodel_image_jobs SET notify_attempts=notify_attempts+1 WHERE update_id=$1 AND next_at=$2",
                                    update_id,lease)
            try:
                async with asyncio.timeout(50):
                    await bot.send_photo(work['external_id'],BufferedInputFile(work['image'],filename=work['filename']),
                                         caption='FIBO 2 · AnyModel · Изображение также доступно в «Моих работах».')
            except (TelegramAPIError,TimeoutError):
                trace_interaction(update_id,'anymodel_image_delivery_failed')
                return
            trace_interaction(update_id,'anymodel_image_delivered')
        await self.pool.execute("UPDATE anymodel_image_jobs SET status='delivered' WHERE update_id=$1 AND next_at=$2",
                                update_id,lease)

    async def loop(self,bot):
        while True:
            try:
                await self.pool.execute("""
                    UPDATE anymodel_image_jobs SET status='unknown'
                    WHERE status='submitting' AND next_at<=now()
                    """)
                if await self.poll_one(bot):
                    continue
            except Exception as error:
                trace_interaction('anymodel-image-worker','anymodel_image_worker_failed',code=type(error).__name__)
            await asyncio.sleep(2)
