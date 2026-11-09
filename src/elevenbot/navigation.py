"""Track only messages published by navigation, including reply keyboard carriers."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from weakref import WeakValueDictionary

from aiogram.exceptions import ClientDecodeError, TelegramAPIError, TelegramBadRequest


@dataclass(frozen=True)
class NavigationState:
    active_id: int | None = None
    animation: str | None = None
    keyboard_id: int | None = None
    keyboard_labels: tuple[str, ...] = ()
    stale_ids: tuple[int, ...] = ()

    def retire(self, message_id, **changes):
        ids = self.stale_ids if message_id is None or message_id in self.stale_ids else (*self.stale_ids, message_id)
        return replace(self, stale_ids=ids, **changes)


class Navigation:
    def __init__(self, pool, bot):
        self.pool, self.bot = pool, bot
        self.memory = {}
        self.locks = WeakValueDictionary()
        self.owners = {}

    @asynccontextmanager
    async def serial(self, chat):
        # The Telegram poller is already single-instance. Also serialize background
        # keyboard updates and direct transitions against the handler for this chat.
        task = asyncio.current_task()
        if self.owners.get(chat) is task:
            yield
            return
        lock = self.locks.setdefault(chat, asyncio.Lock())
        async with lock:
            self.owners[chat] = task
            try:
                yield
            finally:
                del self.owners[chat]

    async def read(self, chat):
        if self.pool is None:
            return self.memory.get(chat, NavigationState())
        row = await self.pool.fetchrow('SELECT * FROM telegram_navigation WHERE chat_id=$1', chat)
        if row is None:
            return NavigationState()
        return NavigationState(row['active_id'], row['animation'], row['keyboard_id'],
                               tuple(row['keyboard_labels']), tuple(row['stale_ids']))

    async def save(self, chat, state):
        if self.pool is None:
            self.memory[chat] = state
            return
        await self.pool.execute("""
            INSERT INTO telegram_navigation(chat_id,active_id,animation,keyboard_id,keyboard_labels,stale_ids)
            VALUES($1,$2,$3,$4,$5,$6)
            ON CONFLICT(chat_id) DO UPDATE SET active_id=excluded.active_id,animation=excluded.animation,
                keyboard_id=excluded.keyboard_id,keyboard_labels=excluded.keyboard_labels,stale_ids=excluded.stale_ids
            """, chat, state.active_id, state.animation, state.keyboard_id, state.keyboard_labels, state.stale_ids)

    async def cleanup(self, chat, state):
        remaining = []
        for message_id in state.stale_ids:
            if message_id in (state.active_id, state.keyboard_id):
                continue
            try:
                if await self.bot.delete_message(chat, message_id):
                    continue
            except TelegramBadRequest as error:
                if 'message to delete not found' in str(error).lower():
                    continue
            except (ClientDecodeError, TelegramAPIError):
                pass
            try:
                await self.bot.edit_message_reply_markup(chat_id=chat,message_id=message_id,reply_markup=None)
            except TelegramBadRequest as error:
                if not any(reason in str(error).lower() for reason in ('message is not modified','message to edit not found')):
                    remaining.append(message_id)
            except (ClientDecodeError, TelegramAPIError):
                remaining.append(message_id)
        if tuple(remaining) != state.stale_ids:
            await self.save(chat, replace(state, stale_ids=tuple(remaining)))
