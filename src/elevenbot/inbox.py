"""Per-chat scheduling of the durable Telegram inbox."""

import asyncio
import json
import time
from collections import defaultdict
from contextvars import ContextVar

from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from aiogram.types import Update

current_navigation = ContextVar('current_navigation', default=None)


def navigation_obsolete():
    check = current_navigation.get()
    return check is not None and check()


class InboxDispatcher:
    def __init__(self, pool, app, is_navigation):
        self.pool = pool
        self.app = app
        self.is_navigation = is_navigation
        self.chats = {}
        self.superseded = set()
        self.active_navigation = {}

    async def schedule(self):
        # Select each chat's first pending events so a flood from one chat cannot hide another.
        db_start = time.monotonic()
        rows = await self.pool.fetch("""
            WITH pending AS (
                SELECT update_id,payload,created_at,
                       COALESCE(payload#>>'{message,chat,id}',
                                payload#>>'{callback_query,message,chat,id}',
                                payload#>>'{callback_query,from_user,id}',
                                payload#>>'{callback_query,from,id}',
                                payload#>>'{pre_checkout_query,from_user,id}',
                                payload#>>'{pre_checkout_query,from,id}',update_id::text) AS chat
                FROM inbox WHERE NOT done AND error_code IS DISTINCT FROM 'RETRY_REVIEW'
            ), ranked AS (
                SELECT *,row_number() OVER (PARTITION BY chat ORDER BY update_id) AS position
                FROM pending
            )
            SELECT update_id,payload,chat,extract(epoch FROM now()-created_at)::float AS queue_age
            FROM ranked WHERE position<=25 ORDER BY position, update_id LIMIT 500
        """)
        db_ms = round((time.monotonic()-db_start)*1000)
        if db_ms >= 100:
            print(json.dumps({'event':'telegram_inbox_db_timing','db_ms':db_ms}),flush=True)
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['chat']].append(row)
        for chat, batch in grouped.items():
            active = self.active_navigation.get(chat)
            if active is not None:
                following = next((row for row in batch if row['update_id'] > active), None)
                if following:
                    next_update = self.decode(following)
                    if next_update is not None and self.is_navigation(next_update):
                        self.superseded.add(active)
            if chat in self.chats or len(self.chats) >= 12:
                continue
            self.chats[chat] = asyncio.create_task(self.drain(chat, batch))
        for chat, task in tuple(self.chats.items()):
            if task.done():
                del self.chats[chat]
                task.result()

    @staticmethod
    def decode(row):
        try:
            return Update.model_validate_json(row['payload'])
        except ValueError:
            return None

    async def drain(self, chat, batch):
        items = []
        for row in batch:
            update = self.decode(row)
            items.append((row, update, update is not None and self.is_navigation(update)))
        for index, (row, update, navigation) in enumerate(items):
            update_id = row['update_id']
            if update is None or navigation and index+1<len(items) and items[index+1][2]:
                await self.done(update_id)
                continue
            start = time.monotonic()
            marker = None
            if navigation:
                self.active_navigation[chat] = update_id
                marker = current_navigation.set(lambda: update_id in self.superseded)
            try:
                try:
                    if navigation:
                        async with asyncio.timeout(10):
                            await self.app.handle(update, from_inbox=True)
                    else:
                        await self.app.handle(update, from_inbox=True)
                except TelegramRetryAfter as error:
                    if navigation:
                        # A rate-limit response is a definite refusal. Keep only the current
                        # navigation event eligible for one bounded repeat.
                        if error.retry_after<=5 and not navigation_obsolete():
                            await asyncio.sleep(error.retry_after)
                            if not navigation_obsolete():
                                try:
                                    async with asyncio.timeout(10):
                                        await self.app.handle(update, from_inbox=True)
                                except (TelegramNetworkError, TelegramServerError, TelegramRetryAfter, TimeoutError):
                                    pass
                    else:
                        await self.retry_later(update_id, max(error.retry_after,1))
                        return
                except (TelegramNetworkError, TelegramServerError, TimeoutError):
                    if not navigation:
                        await self.retry_later(update_id, 3)
                        return
                except (ValueError, TypeError, IndexError):
                    pass
                except Exception as error:
                    print(json.dumps({'event':'update_failed','error_type':type(error).__name__}),flush=True)
                    if not navigation:
                        await self.retry_later(update_id, 3)
                        return
                await self.done(update_id)
            finally:
                if marker is not None:
                    current_navigation.reset(marker)
                    self.active_navigation.pop(chat, None)
                self.superseded.discard(update_id)
            elapsed = time.monotonic()-start
            if row['queue_age'] >= 2 or elapsed >= 2:
                print(json.dumps({'event':'telegram_update_timing','navigation':navigation,
                                  'queue_ms':round(row['queue_age']*1000),'handler_ms':round(elapsed*1000)}),flush=True)

    async def retry_later(self, update_id, delay):
        tries = await self.pool.fetchval("""
            UPDATE inbox SET dispatch_attempts=dispatch_attempts+1,
                error_code=CASE WHEN dispatch_attempts>=2 THEN 'RETRY_REVIEW' ELSE error_code END
            WHERE update_id=$1 RETURNING dispatch_attempts
            """,update_id)
        if tries < 3:
            await asyncio.sleep(delay)
        else:
            print(json.dumps({'event':'telegram_inbox_review','update_id':update_id}),flush=True)

    async def done(self, update_id):
        await self.pool.execute('UPDATE inbox SET done=true WHERE update_id=$1', update_id)

    async def close(self):
        tasks = list(self.chats.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
