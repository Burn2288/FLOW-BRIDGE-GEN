"""One durable dispatch boundary shared by registered execution adapters."""

from dataclasses import dataclass
from typing import Protocol

from .core import Rejected
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
    def __init__(self,pricing,adapters):
        self.pricing,self.adapters = pricing,adapters

    async def confirm(self,user,external,quote_id,update_id,*,progress,background):
        cfg = self.pricing.config
        pool = self.pricing.pool

        adapter = prepared = None
        async def prepare(conn,quote):
            nonlocal adapter,prepared
            # Paid pilot eligibility is independent of the Admin Edition session.
            if cfg.access_mode!='private' or cfg.payments_enabled or external not in cfg.admin_ids:
                raise Rejected('Тестовый запуск для этого аккаунта недоступен.')
            await self.pricing.admin(conn,user,external)
            from .model_policy import admitted
            req = quote.request
            if not await admitted(conn,req.provider,req.model,req.operation):
                raise Rejected('Модель не допущена к этой операции.')
            adapter = self.adapters.get(quote.request.provider)
            if adapter is None:
                raise Rejected('Агрегатор недоступен.')
            prepared = await adapter.prepare(conn,user,external,quote,update_id)
            await conn.execute("INSERT INTO task_dispatch VALUES($1,'pending',false)",quote.id)
            await reserve_task_tokens(conn,user,quote.id,int(quote.price['total']))

        quote,accepted = await self.pricing.confirm(user,quote_id,update_id,prepare,live_wallet=True)
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
            except Exception:
                async with pool.acquire() as conn, conn.transaction():
                    await conn.execute("UPDATE task_dispatch SET state='uncertain' WHERE quote_id=$1",quote.id)
                    await settle_task_tokens(conn,quote.id)
                raise
            async with pool.acquire() as conn, conn.transaction():
                await conn.execute('UPDATE task_dispatch SET state=$2 WHERE quote_id=$1',
                                   quote.id,'delegated' if kind else 'completed')
                await settle_task_tokens(conn,quote.id)
            return result

        if kind:
            return quote,True,await dispatch(lambda job:background(request,kind,job))
        async with progress(request):
            result = await dispatch()
        return quote,True,result


async def recover_interrupted(pool):
    # Called once after acquiring the Telegram polling lock. Never replays a POST.
    await pool.execute("""
        UPDATE task_dispatch d SET state=CASE
            WHEN d.state='pending' THEN 'interrupted'
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
    from aiogram.exceptions import TelegramAPIError
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
        try:
            await bot.send_message(row['external_id'],f"⚠️ {row['title']} · {detail} Автоповтора нет.")
        except TelegramAPIError:
            continue
        await pool.execute("UPDATE task_dispatch SET recovery_notice=false WHERE quote_id=$1",row['quote_id'])
