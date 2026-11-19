"""One durable dispatch boundary shared by registered execution adapters."""

from dataclasses import dataclass
from typing import Protocol

from .core import Rejected
from .submission import ProviderRefused
from .task_wallet import reserve_task_tokens,settle_task_tokens


@dataclass
class Outcome:
    kind: str
    value: object
    label: str = ''


class ExecutionAdapter(Protocol):
    def background(self, operation): ...
    async def prepare(self,conn,user,external,quote,update_id): ...
    async def run(self,user,quote,update_id,prepared,on_accepted): ...


class TaskLaunch:
    def __init__(self,pricing,adapters,*,authorize=None):
        self.pricing,self.adapters = pricing,adapters
        self.authorize = authorize

    async def authorize_pilot(self,conn,user,external):
        # Paid pilot eligibility is independent of the Admin Edition session.
        cfg = self.pricing.config
        if cfg.access_mode!='private' or cfg.payments_enabled or external not in cfg.admin_ids:
            raise Rejected('Тестовый запуск для этого аккаунта недоступен.')
        await self.pricing.admin(conn,user,external)

    async def authorize_request(self, conn, user, external, request):
        if self.authorize is not None:
            await self.authorize(conn, user, external)
            return
        cfg = self.pricing.config
        if cfg.allows_public_image(request.provider, request.model, request.operation):
            from .core import Service
            await Service(self.pricing.pool, cfg).authorize(conn, user)
            linked = await conn.fetchval(
                "SELECT user_id FROM identities WHERE platform='telegram' AND external_id=$1", external
            )
            halted = await conn.fetchval("SELECT halted FROM settings WHERE id=1 FOR SHARE")
            if linked != user or not cfg.generation_enabled or halted is not False:
                raise Rejected('Запуск изображения пока недоступен.')
            return
        await self.authorize_pilot(conn, user, external)

    async def confirm(self,user,external,quote_id,update_id,*,progress,background,defer=None):
        pool = self.pricing.pool

        adapter = prepared = None
        async def validate(conn, request):
            from .model_policy import admitted
            from .model_capabilities import validate_pinned
            if request.operation=='audio.generate' or not await admitted(conn,request.provider,request.model,request.operation):
                raise Rejected('Модель не допущена к этой операции.')
            await validate_pinned(conn, request)

        async def prepare(conn,quote):
            nonlocal adapter,prepared
            await self.authorize_request(conn,user,external,quote.request)
            adapter = self.adapters.get(quote.request.provider)
            if adapter is None:
                raise Rejected('Агрегатор недоступен.')
            prepared = await adapter.prepare(conn,user,external,quote,update_id)
            await conn.execute("INSERT INTO task_dispatch VALUES($1,'pending',false)",quote.id)
            await reserve_task_tokens(conn,user,quote.id,int(quote.price['total']))

        quote,accepted = await self.pricing.confirm(user,quote_id,update_id,prepare,live_wallet=True,validate=validate)
        if not accepted:
            return quote,False,None
        request = quote.request
        kind = adapter.background(request.operation)

        async def dispatch(on_accepted=None):
            claimed = await pool.fetchval("""
                UPDATE task_dispatch SET state='dispatching' WHERE quote_id=$1 AND state='pending'
                RETURNING quote_id
                """,quote.id)
            if not claimed:
                raise Rejected('Задача уже принята. Повтора не будет.')
            try:
                result = await adapter.run(user,quote,update_id,prepared,on_accepted)
            except Exception as error:
                state='rejected' if isinstance(error,ProviderRefused) else 'uncertain'
                async with pool.acquire() as conn, conn.transaction():
                    await conn.execute('UPDATE task_dispatch SET state=$2 WHERE quote_id=$1',quote.id,state)
                    await settle_task_tokens(conn,quote.id)
                raise
            async with pool.acquire() as conn, conn.transaction():
                await conn.execute('UPDATE task_dispatch SET state=$2 WHERE quote_id=$1',
                                   quote.id,'delegated' if kind else 'completed')
                await settle_task_tokens(conn,quote.id)
            return result

        async def run():
            if kind:
                return await dispatch(lambda job:background(request,kind,job))
            async with progress(request):
                return await dispatch()

        if defer is not None:
            defer(quote, run)
            return quote,True,None
        return quote,True,await run()


async def recover_interrupted(pool):
    # Called once after acquiring the Telegram polling lock. Never replays a POST.
    await pool.execute("""
        UPDATE task_dispatch d SET state=CASE
            WHEN d.state='pending' THEN 'interrupted'
            WHEN EXISTS(SELECT 1 FROM video_jobs v WHERE v.id=d.quote_id AND v.status='failed' AND v.provider_id IS NULL)
              THEN 'rejected'
            WHEN EXISTS(SELECT 1 FROM video_jobs v WHERE v.id=d.quote_id AND v.provider_id IS NOT NULL)
              OR EXISTS(SELECT 1 FROM anymodel_image_jobs i WHERE i.update_id=q.update_id
                        AND (i.provider_id IS NOT NULL OR i.status IN ('ready','delivered')))
              THEN 'delegated'
            WHEN EXISTS(SELECT 1 FROM task_chat_works w WHERE w.quote_id=d.quote_id)
              OR EXISTS(SELECT 1 FROM task_speech_works s WHERE s.id=d.quote_id AND s.audio IS NOT NULL)
              OR EXISTS(SELECT 1 FROM image_works i WHERE i.update_id=q.update_id) THEN 'completed'
            ELSE 'uncertain' END,
            recovery_notice=true
        FROM task_price_quotes q WHERE q.id=d.quote_id AND d.state IN ('pending','dispatching')
        """)
    await settle_task_tokens(pool)


async def notify_interrupted(pool,bot):
    import asyncio
    from aiogram.exceptions import ClientDecodeError, TelegramAPIError, TelegramRetryAfter
    rows = await pool.fetch("""
        SELECT d.quote_id,d.state,i.external_id,q.request->>'title' AS title
        FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id
        JOIN users u ON u.id=q.user_id AND NOT u.blocked
        JOIN identities i ON i.user_id=u.id AND i.platform='telegram' AND i.accepted_at IS NOT NULL
        WHERE d.recovery_notice AND d.state IN ('interrupted','uncertain') LIMIT 20
        """)
    for row in rows:
        detail = ('Задача остановлена до отправки после перезапуска.' if row['state']=='interrupted'
                  else 'Исход запуска после перезапуска неизвестен.')
        claimed = await pool.fetchval("""
            UPDATE task_dispatch SET recovery_notice=false WHERE quote_id=$1 AND recovery_notice
            RETURNING true
            """,row['quote_id'])
        if not claimed:
            continue
        try:
            async with asyncio.timeout(8):
                await bot.send_message(row['external_id'],f"⚠️ {row['title']} · {detail} Автоповтора нет.")
        except TelegramRetryAfter as error:
            await pool.execute("UPDATE task_dispatch SET recovery_notice=true WHERE quote_id=$1",row['quote_id'])
            await asyncio.sleep(max(error.retry_after, 1))
            return
        except (ClientDecodeError, TelegramAPIError, TimeoutError):
            # Telegram may have received the message. The task state remains in PostgreSQL.
            pass
