"""Task messages owned independently of Telegram navigation."""

import asyncio
from contextlib import asynccontextmanager

from aiogram.exceptions import ClientDecodeError, TelegramAPIError, TelegramBadRequest

from .core import Rejected
from .interaction import trace_interaction

WAITING = {
    'video': 'Генерирую видео…',
    'images.generate': 'Генерирую изображение…',
    'audio.speech': 'Озвучиваю текст…',
    'chat': 'Готовлю ответ…',
}
UNKNOWN = 'Исход запроса неизвестен. Автоповтора нет.'


class ReportedTaskError(Rejected):
    """The task message already contains the user-facing failure."""


class TaskProgress:
    def __init__(self, bot, pool=None):
        self.bot = bot
        self.pool = pool

    async def start(self, chat, model, operation, *, video_id=None, image_id=None):
        text = f'⏳ {model} · {WAITING[operation]}'
        try:
            async with asyncio.timeout(6):
                message = await self.bot.send_message(chat, text)
        except (TelegramAPIError, ClientDecodeError, TimeoutError) as error:
            trace_interaction(None, 'task_status_send_failed', error_type=type(error).__name__)
            return None
        if video_id is not None or image_id is not None:
            try:
                await self.pool.execute("""
                    INSERT INTO task_progress(chat_id,message_id,model,video_id,image_id,last_text)
                    VALUES($1,$2,$3,$4,$5,$6)
                    """, chat, message.message_id, model, video_id, image_id, text)
            except Exception:
                await self.finish(chat,message.message_id,model,'Статус задания недоступен.')
                trace_interaction(None, 'task_status_link_failed')
        return message.message_id

    async def edit(self, chat, message, text):
        if message is None:
            return False
        try:
            async with asyncio.timeout(6):
                await self.bot.edit_message_text(text, chat_id=chat, message_id=message)
        except TelegramBadRequest as error:
            if 'message is not modified' in str(error).lower():
                return True
            if 'message to edit not found' in str(error).lower():
                return True
            trace_interaction(None, 'task_status_edit_failed', error_type=type(error).__name__)
            return False
        except (TelegramAPIError, ClientDecodeError, TimeoutError) as error:
            trace_interaction(None, 'task_status_edit_failed', error_type=type(error).__name__)
            return False
        return True

    async def finish(self, chat, message, model, outcome='Готово.', *, success=False):
        icon = '✅' if success else '⚠️'
        return await self.edit(chat,message,f'{icon} {model} · {outcome}')

    @asynccontextmanager
    async def track(self, chat, model, operation):
        message = await self.start(chat,model,operation)
        try:
            yield
        except Rejected as error:
            if await self.finish(chat,message,model,str(error)):
                raise ReportedTaskError(str(error)) from None
            raise
        except Exception:
            await self.finish(chat,message,model,UNKNOWN)
            raise
        else:
            await self.finish(chat,message,model,success=True)

    async def refresh(self):
        rows = await self.pool.fetch("""
            SELECT p.*,v.status AS video_status,v.provider_stage,v.provider_progress,v.notify_at,
                   i.status AS image_status,COALESCE(v.notify_attempts,i.notify_attempts) AS attempts,
                   COALESCE(v.expires_at,i.expires_at)<=now() AS expired
            FROM task_progress p
            LEFT JOIN video_jobs v ON v.id=p.video_id
            LEFT JOIN anymodel_image_jobs i ON i.update_id=p.image_id
            """)
        for row in rows:
            state = row['video_status'] or row['image_status']
            operation = 'video' if row['video_id'] is not None else 'images.generate'
            success = (state == 'delivered' or state == 'succeeded' and row['notify_at'] is None)
            terminal = True
            if success:
                outcome = 'Готово.'
            elif state in ('uncertain','unknown') or row['expired']:
                outcome = UNKNOWN
            elif state == 'failed':
                outcome = 'Не удалось завершить задачу.'
            elif state in ('ready','succeeded') and row['attempts'] >= 3:
                outcome = 'Результат сохранён в «Моих работах». Доставка не подтверждена.'
            else:
                terminal = False
                outcome = WAITING[operation]
                if state in ('polling','pending'):
                    outcome = {'queued':'В очереди у провайдера…',
                               'processing':WAITING[operation]}.get(row['provider_stage'], 'Жду результат от провайдера…')
                elif state in ('ready','succeeded'):
                    outcome = 'Результат готов. Отправляю в Telegram…'
                if row['provider_progress'] is not None and state == 'polling':
                    outcome += f' {row["provider_progress"]}%'
            icon = '✅' if success else '⚠️' if terminal else '⏳'
            text = f'{icon} {row["model"]} · {outcome}'
            if text == row['last_text'] or not await self.edit(row['chat_id'],row['message_id'],text):
                continue
            if terminal:
                await self.pool.execute('DELETE FROM task_progress WHERE chat_id=$1 AND message_id=$2',
                                        row['chat_id'],row['message_id'])
            else:
                await self.pool.execute('UPDATE task_progress SET last_text=$3 WHERE chat_id=$1 AND message_id=$2',
                                        row['chat_id'],row['message_id'],text)

    async def loop(self):
        while True:
            try:
                await self.refresh()
            except Exception as error:
                trace_interaction(None, 'task_status_refresh_failed', error_type=type(error).__name__)
            await asyncio.sleep(2)
