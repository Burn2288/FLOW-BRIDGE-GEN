"""Private Telegram broadcasts with a durable, at-most-once delivery queue."""

import asyncio
import json
from uuid import UUID, uuid4

import asyncpg
from aiogram.exceptions import (
    ClientDecodeError,
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from aiogram.types import MessageEntity

from .core import Rejected


ROUTES = {'brlist', 'brnew', 'brview', 'brreplace', 'braudience', 'brself', 'brall',
          'brconfirm', 'brcancel', 'brstop'}
RECIPIENTS = """
    SELECT i.external_id FROM identities i JOIN users u ON u.id=i.user_id
    WHERE i.platform='telegram' AND i.telegram_private AND i.terms_version='1'
      AND i.accepted_at IS NOT NULL AND NOT i.broadcast_opt_out AND NOT u.blocked
      AND ($1='all' OR i.external_id=$2)
"""
STALE = 'Кнопка рассылки устарела. Откройте «📣 Рассылки».'


async def send_post(bot, chat, row, markup=None):
    entities = [MessageEntity.model_validate(entity) for entity in json.loads(row['entities'])]
    if row['photo_id']:
        return await bot.send_photo(chat, row['photo_id'], caption=row['body'],
                                    caption_entities=entities, reply_markup=markup)
    return await bot.send_message(chat, row['body'], entities=entities, reply_markup=markup)


class Broadcasts:
    def __init__(self, pool):
        self.pool = pool

    async def observe_private(self, chat):
        await self.pool.execute("""
            UPDATE identities SET telegram_private=true
            WHERE platform='telegram' AND external_id=$1 AND NOT telegram_private
            """, chat)

    async def preference(self, chat, opt_out=None):
        if opt_out is None:
            return await self.pool.fetchval("""
                SELECT broadcast_opt_out FROM identities WHERE platform='telegram' AND external_id=$1
                """, chat)
        return await self.pool.fetchval("""
            UPDATE identities SET broadcast_opt_out=$2 WHERE platform='telegram' AND external_id=$1
            RETURNING broadcast_opt_out
            """, chat, opt_out)

    async def recent(self, chat):
        return await self.pool.fetch("""
            SELECT * FROM telegram_broadcasts WHERE owner_chat=$1 AND state<>'cancelled'
            ORDER BY (state='draft') DESC, (state='running') DESC, created_at DESC LIMIT 8
            """, chat)

    async def draft(self, chat):
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("""
                INSERT INTO telegram_broadcasts(id,owner_chat) VALUES($1,$2)
                ON CONFLICT(owner_chat) WHERE state='draft' DO NOTHING
                """, uuid4(), chat)
            return await conn.fetchrow("""
                SELECT * FROM telegram_broadcasts WHERE owner_chat=$1 AND state='draft'
                """, chat)

    async def get(self, chat, id, revision=None):
        row = await self.pool.fetchrow(
            'SELECT * FROM telegram_broadcasts WHERE id=$1 AND owner_chat=$2', id, chat,
        )
        if not row or (revision is not None and revision != row['revision']):
            raise Rejected(STALE)
        return row

    async def replace(self, chat, id, revision):
        row = await self.pool.fetchrow("""
            UPDATE telegram_broadcasts SET awaiting_post=true,revision=revision+1,
                audience=NULL,expected_count=NULL
            WHERE id=$1 AND owner_chat=$2 AND revision=$3 AND state='draft' RETURNING *
            """, id, chat, revision)
        if not row:
            raise Rejected(STALE)
        return row

    async def save_post(self, chat, id, revision, message):
        if not message or message.media_group_id or not (message.photo or message.text):
            raise Rejected('Пришлите текст или одну фотографию с подписью.')
        if message.photo:
            body, photo_id, entities = message.caption, message.photo[-1].file_id, message.caption_entities
            if not body or not body.strip():
                raise Rejected('Добавьте подпись к фотографии.')
        else:
            body, photo_id, entities = message.text, None, message.entities
        if not body.strip():
            raise Rejected('Добавьте текст рассылки.')
        row = await self.pool.fetchrow("""
            UPDATE telegram_broadcasts SET body=$4,photo_id=$5,entities=$6::jsonb,awaiting_post=false,
                revision=revision+1,audience=NULL,expected_count=NULL
            WHERE id=$1 AND owner_chat=$2 AND revision=$3 AND state='draft' AND awaiting_post RETURNING *
            """, id, chat, revision, body, photo_id,
            json.dumps([entity.model_dump(mode='json', exclude_none=True) for entity in (entities or ())]))
        if not row:
            raise Rejected(STALE)
        return row

    async def select_audience(self, chat, id, revision, audience):
        row = await self.pool.fetchrow(f"""
            UPDATE telegram_broadcasts SET audience=$1,revision=revision+1,
                expected_count=(SELECT count(*) FROM ({RECIPIENTS}) recipients)
            WHERE id=$3 AND owner_chat=$2 AND revision=$4 AND state='draft' AND NOT awaiting_post
            RETURNING *
            """, audience, chat, id, revision)
        if not row:
            raise Rejected(STALE)
        return row

    async def confirm(self, chat, id, revision):
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow("""
                SELECT * FROM telegram_broadcasts WHERE id=$1 AND owner_chat=$2 FOR UPDATE
                """, id, chat)
            if not row or row['revision'] != revision or row['state'] == 'cancelled':
                raise Rejected(STALE)
            if row['state'] != 'draft':
                return row
            if row['awaiting_post'] or not row['audience'] or not row['expected_count']:
                raise Rejected('Сначала выберите получателей.')
            recipients = await conn.fetch(RECIPIENTS, row['audience'], chat)
            if len(recipients) != row['expected_count']:
                return await conn.fetchrow("""
                    UPDATE telegram_broadcasts SET expected_count=$2,revision=revision+1
                    WHERE id=$1 RETURNING *
                    """, id, len(recipients))
            await conn.execute("""
                INSERT INTO telegram_broadcast_deliveries(broadcast_id,chat_id)
                SELECT $1, unnest($2::bigint[])
                """, id, [recipient['external_id'] for recipient in recipients])
            return await conn.fetchrow("""
                UPDATE telegram_broadcasts SET state='running',changed_at=clock_timestamp()
                WHERE id=$1 RETURNING *
                """, id)

    async def cancel(self, chat, id, revision):
        cancelled = await self.pool.fetchval("""
            UPDATE telegram_broadcasts SET state='cancelled'
            WHERE id=$1 AND owner_chat=$2 AND revision=$3 AND state='draft' RETURNING true
            """, id, chat, revision)
        if not cancelled:
            raise Rejected(STALE)

    async def stop(self, chat, id):
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow("""
                SELECT state FROM telegram_broadcasts WHERE id=$1 AND owner_chat=$2 FOR UPDATE
                """, id, chat)
            if not row or row['state'] not in ('running', 'done', 'stopped'):
                raise Rejected(STALE)
            if row['state'] == 'running':
                await conn.execute("UPDATE telegram_broadcast_deliveries SET status='stopped' "
                                   "WHERE broadcast_id=$1 AND status='pending'", id)
                await conn.execute("UPDATE telegram_broadcasts SET state='stopped',changed_at=clock_timestamp() "
                                   "WHERE id=$1", id)

    async def claim(self):
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow("""
                SELECT b.* FROM telegram_broadcasts b WHERE b.state='running'
                  AND (SELECT resume_at<=now() FROM telegram_broadcast_throttle)
                  AND EXISTS (SELECT 1 FROM telegram_broadcast_deliveries d
                              WHERE d.broadcast_id=b.id AND d.status='pending' AND d.retry_at<=now())
                ORDER BY b.created_at LIMIT 1 FOR UPDATE OF b
                """)
            if not row:
                return None
            chat = await conn.fetchval("""
                SELECT chat_id FROM telegram_broadcast_deliveries WHERE broadcast_id=$1
                  AND status='pending' AND retry_at<=now() ORDER BY chat_id LIMIT 1
                """, row['id'])
            if chat is None:
                return None
            eligible = await conn.fetchval(f"""
                SELECT EXISTS ({RECIPIENTS})
                """, 'self', chat)
            await conn.execute("""
                UPDATE telegram_broadcast_deliveries SET status=$3 WHERE broadcast_id=$1 AND chat_id=$2
                """, row['id'], chat, 'sending' if eligible else 'opted_out')
            if not eligible:
                await self.finish_if_empty(conn, row['id'])
            return row, chat, eligible

    async def finish_if_empty(self, conn, id):
        await conn.execute("""
            UPDATE telegram_broadcasts SET changed_at=clock_timestamp(),
                state=CASE WHEN state='running' AND NOT EXISTS (
                    SELECT 1 FROM telegram_broadcast_deliveries WHERE broadcast_id=$1
                      AND status IN ('pending','sending')
                ) THEN 'done' ELSE state END WHERE id=$1
            """, id)

    async def complete(self, id, chat, status, message_id=None, retry_after=None):
        async with self.pool.acquire() as conn, conn.transaction():
            state = await conn.fetchval('SELECT state FROM telegram_broadcasts WHERE id=$1 FOR UPDATE', id)
            if retry_after is not None:
                await self.pause(conn, retry_after)
                status = 'pending' if state == 'running' else 'stopped'
            await conn.execute("""
                UPDATE telegram_broadcast_deliveries SET status=$3,message_id=$4,
                    retry_at=now()+make_interval(secs=>$5)
                WHERE broadcast_id=$1 AND chat_id=$2 AND status='sending'
                """, id, chat, status, message_id, retry_after or 0)
            await self.finish_if_empty(conn, id)

    @staticmethod
    async def pause(conn, seconds):
        await conn.execute("""
            UPDATE telegram_broadcast_throttle
            SET resume_at=greatest(resume_at,now()+make_interval(secs=>$1))
            """, max(1, seconds))

    async def recover(self):
        async with self.pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch("""
                UPDATE telegram_broadcast_deliveries SET status='unknown'
                WHERE status='sending' RETURNING broadcast_id
                """)
            for id in {row['broadcast_id'] for row in rows}:
                await self.finish_if_empty(conn, id)

    async def counts(self, id):
        rows = await self.pool.fetch("""
            SELECT status,count(*) AS n FROM telegram_broadcast_deliveries
            WHERE broadcast_id=$1 GROUP BY status
            """, id)
        return {row['status']: row['n'] for row in rows}

    async def attach_report(self, id, message_id):
        await self.pool.execute("""
            UPDATE telegram_broadcasts SET report_id=$2,report_at=NULL WHERE id=$1
            """, id, message_id)

    async def next_report(self):
        return await self.pool.fetchrow("""
            SELECT * FROM telegram_broadcasts WHERE report_id IS NOT NULL
              AND (SELECT resume_at<=now() FROM telegram_broadcast_throttle)
              AND (report_at IS NULL OR (report_at<changed_at
                AND (state<>'running' OR report_at<now()-interval '5 seconds')))
            ORDER BY changed_at LIMIT 1
            """)

    async def reported(self, row):
        await self.pool.execute("""
            UPDATE telegram_broadcasts SET report_at=greatest($3,clock_timestamp()-interval '1 second')
            WHERE id=$1 AND report_id=$2
            """, row['id'], row['report_id'], row['changed_at'])


def report_text(counts):
    def count(status):
        return counts.get(status, 0)
    return (f"📣 Рассылка\nОтправлено {count('sent')} из {sum(counts.values())}"
            f" · {count('unavailable')} недоступны · {count('error')} ошибки"
            f"\nВ очереди: {count('pending')} · Отправляется: {count('sending')}"
            f"\nОстановлено: {count('stopped')} · Исход неизвестен: {count('unknown')}"
            f" · Отключили рассылки или потеряли доступ: {count('opted_out')}")


class BroadcastWorker:
    def __init__(self, queue, bot, buttons):
        self.queue, self.bot, self.buttons = queue, bot, buttons

    async def deliver(self, claim):
        row, chat, eligible = claim
        if not eligible:
            return
        id = row['id']
        try:
            message = await send_post(self.bot, chat, row)
        except TelegramRetryAfter as error:
            await self.queue.complete(id, chat, 'pending', retry_after=max(1, error.retry_after))
        except (TelegramForbiddenError, TelegramNotFound):
            await self.queue.complete(id, chat, 'unavailable')
        except TelegramBadRequest as error:
            status = 'unavailable' if 'chat not found' in str(error).lower() else 'error'
            await self.queue.complete(id, chat, status)
        except TelegramUnauthorizedError:
            await self.queue.complete(id, chat, 'error')
        except (ClientDecodeError, TelegramAPIError, TimeoutError, OSError):
            await self.queue.complete(id, chat, 'unknown')
        else:
            await self.queue.complete(id, chat, 'sent', message_id=message.message_id)

    def report_buttons(self, row):
        rows = [[('Остановить рассылку', f"brstop:{row['id']}")]] if row['state'] == 'running' else []
        return self.buttons(rows + [[('← К рассылкам', 'brlist')]])

    async def report(self, row):
        try:
            await self.bot.edit_message_text(
                report_text(await self.queue.counts(row['id'])), chat_id=row['owner_chat'],
                message_id=row['report_id'], reply_markup=self.report_buttons(row),
            )
        except TelegramRetryAfter as error:
            await self.queue.pause(self.queue.pool, error.retry_after)
            return
        except (ClientDecodeError, TelegramAPIError):
            pass
        await self.queue.reported(row)

    async def loop(self):
        while True:
            try:
                async with self.queue.pool.acquire() as lock:
                    if await lock.fetchval('SELECT pg_try_advisory_lock(921189)'):
                        try:
                            await self.queue.recover()
                            while True:
                                row = await self.queue.next_report()
                                if row:
                                    await self.report(row)
                                claim = await self.queue.claim()
                                if claim:
                                    await self.deliver(claim)
                                await asyncio.sleep(1.05 if claim or row else 0.75)
                        finally:
                            await lock.execute('SELECT pg_advisory_unlock(921189)')
            except (asyncpg.PostgresError, TimeoutError, OSError):
                pass
            await asyncio.sleep(3)


class BroadcastUI:
    def __init__(self, app, queue, buttons):
        self.app, self.queue, self.buttons = app, queue, buttons

    def authorize(self, chat):
        if not self.app.has_admin_session(chat):
            raise Rejected(self.app.admin_denial(chat))

    async def preference(self, chat, opt_out=None):
        disabled = await self.queue.preference(chat, opt_out)
        label, action = ('Включить рассылки', 'bron') if disabled else ('Отключить рассылки', 'broff')
        await self.app.catalogue_screen(
            chat, 'Рассылки отключены.' if disabled else 'Рассылки включены.',
            self.buttons([[(label, action)], [('← Помощь', 'section:3')]]),
        )

    async def list(self, user, chat):
        await self.app.svc.conversation(user, 'home')
        states = {'draft': 'Продолжить черновик', 'running': 'Идёт', 'done': 'Завершена', 'stopped': 'Остановлена'}
        rows = [[('Создать рассылку', 'brnew')]]
        for row in await self.queue.recent(chat):
            label = states[row['state']]
            if row['state'] != 'draft':
                label += f" · {str(row['id'])[:8]}"
            rows.append([(label, f"brview:{row['id']}")])
        await self.app.catalogue_screen(chat, '📣 Рассылки', self.buttons(rows + [[('← Назад', 'providers')]]))

    async def request_post(self, user, chat, row):
        key = f"{row['id']}:{row['revision']}"
        await self.app.svc.aggregate_context(user, {'broadcast_post': key})
        await self.app.catalogue_screen(chat, 'Пришлите текст или одну фотографию с подписью.',
                                        self.buttons([[('Отменить', f'brcancel:{key}')]]))

    async def post(self, user, chat, key, message):
        self.authorize(chat)
        id, revision = key.split(':')
        row = await self.queue.save_post(chat, UUID(id), int(revision), message)
        await self.app.svc.conversation(user, 'home')
        await self.preview(chat, row)

    async def preview(self, chat, row):
        key = f"{row['id']}:{row['revision']}"
        await send_post(self.app.bot, chat, row, self.buttons([
            [('Заменить пост', f'brreplace:{key}')], [('Выбрать получателей', f'braudience:{key}')],
            [('Отменить', f'brcancel:{key}')],
        ]))

    async def confirm_screen(self, chat, row):
        key = f"{row['id']}:{row['revision']}"
        count = row['expected_count']
        audience = 'Только мне' if row['audience'] == 'self' else 'Все пользователи, принявшие условия'
        rows = [[(f'Разослать · {count} получ.', f'brconfirm:{key}')]] if count else []
        rows.extend([[('Выбрать получателей', f'braudience:{key}')], [('Отменить', f'brcancel:{key}')]])
        await self.app.catalogue_screen(chat, f'{audience}\nПолучателей: {count}', self.buttons(rows))

    async def show_report(self, chat, row):
        worker = BroadcastWorker(self.queue, self.app.bot, self.buttons)
        if row['report_id'] is not None:
            await worker.report(row)
            return
        message = await self.app.say(chat, report_text(await self.queue.counts(row['id'])),
                                     worker.report_buttons(row))
        await self.queue.attach_report(row['id'], message.message_id)

    async def callback(self, user, chat, route, argument):
        self.authorize(chat)
        await self.app.svc.authorize(self.app.pool, user)
        if route == 'brlist':
            await self.list(user, chat)
            return
        if route == 'brnew':
            row = await self.queue.draft(chat)
            if row['awaiting_post']:
                await self.request_post(user, chat, row)
            else:
                await self.preview(chat, row)
            return
        value, _, version = argument.partition(':')
        id, revision = UUID(value), int(version) if version else None
        if route == 'brview':
            row = await self.queue.get(chat, id)
            if row['state'] != 'draft':
                await self.show_report(chat, row)
            elif row['awaiting_post']:
                await self.request_post(user, chat, row)
            else:
                await self.preview(chat, row)
        elif route == 'brreplace':
            await self.request_post(user, chat, await self.queue.replace(chat, id, revision))
        elif route == 'braudience':
            row = await self.queue.get(chat, id, revision)
            if row['state'] != 'draft' or row['awaiting_post']:
                raise Rejected(STALE)
            key = f'{id}:{revision}'
            await self.app.catalogue_screen(chat, 'Выберите получателей.', self.buttons([
                [('Только мне', f'brself:{key}')],
                [('Все пользователи, принявшие условия', f'brall:{key}')],
                [('Отменить', f'brcancel:{key}')],
            ]))
        elif route in ('brself', 'brall'):
            row = await self.queue.select_audience(chat, id, revision, 'self' if route == 'brself' else 'all')
            await self.confirm_screen(chat, row)
        elif route == 'brconfirm':
            row = await self.queue.confirm(chat, id, revision)
            if row['state'] == 'draft':
                await self.confirm_screen(chat, row)
            else:
                await self.list(user, chat)
                await self.show_report(chat, row)
        elif route == 'brcancel':
            await self.queue.cancel(chat, id, revision)
            await self.list(user, chat)
        elif route == 'brstop':
            await self.queue.stop(chat, id)
            await self.show_report(chat, await self.queue.get(chat, id))
