import asyncio
import time
from types import SimpleNamespace

from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from aiogram.methods import GetUpdates, SendMessage

from elevenbot.inbox import InboxDispatcher, navigation_obsolete
from elevenbot.telegram import MENU, is_navigation_update, receive_updates
from test_admin_access import event


async def add(pool, update):
    await pool.execute('INSERT INTO inbox(update_id,payload) VALUES($1,$2) ON CONFLICT DO NOTHING',
                       update.update_id, update.model_dump_json())


async def until(predicate):
    async with asyncio.timeout(4):
        while not await predicate():
            await asyncio.sleep(0.01)


async def test_slow_chat_does_not_block_new_chat_and_newest_panel_wins(env):
    pool, *_ = env
    started = asyncio.Event()
    resume = asyncio.Event()
    shown = []
    clock = time.monotonic()
    delays = {}

    async def handle(update, *, from_inbox):
        if update.update_id == 1:
            started.set()
            await resume.wait()
        if not navigation_obsolete():
            shown.append((update.message.chat.id, update.message.text))
            delays[update.update_id] = round((time.monotonic()-clock)*1000)

    dispatcher = InboxDispatcher(pool, SimpleNamespace(handle=handle), is_navigation_update)
    try:
        await add(pool,event(1,MENU[0]))
        await dispatcher.schedule()
        await asyncio.wait_for(started.wait(),1)
        for number,text,chat in [(2,MENU[0],100),(3,MENU[0],100),(4,MENU[1],100),(5,'/menu',101)]:
            await add(pool,event(number,text,chat=chat))

        async def scheduled():
            await dispatcher.schedule()
            return (101,'/menu') in shown

        await until(scheduled)
        await asyncio.sleep(.25)
        assert shown == [(101,'/menu')]
        resume.set()

        async def settled():
            await dispatcher.schedule()
            return await pool.fetchval('SELECT count(*)=0 FROM inbox WHERE NOT done')

        await until(settled)
        # A redelivered update remains completed even after replacing the dispatcher.
        await add(pool,event(5,'/menu',chat=101))
        await InboxDispatcher(pool, SimpleNamespace(handle=handle), is_navigation_update).schedule()
        assert shown == [(101,'/menu'),(100,MENU[1])]
        print('isolated_navigation_ms',delays)
    finally:
        await dispatcher.close()


async def test_navigation_429_and_unknown_send_do_not_accumulate(env):
    pool, *_ = env
    attempts = []
    method = SendMessage(chat_id=100,text='fixture')

    async def handle(update, *, from_inbox):
        attempts.append(update.update_id)
        if update.update_id == 1 and attempts.count(1)==1:
            raise TelegramRetryAfter(method,'fixture',1)
        if update.update_id == 1:
            raise TelegramNetworkError(method,'unknown send outcome')

    dispatcher = InboxDispatcher(pool,SimpleNamespace(handle=handle),is_navigation_update)
    try:
        await add(pool,event(1,'/menu'))
        await dispatcher.schedule()

        async def settled():
            await dispatcher.schedule()
            return await pool.fetchval('SELECT done FROM inbox WHERE update_id=1')

        await until(settled)
        await dispatcher.close()
        dispatcher = InboxDispatcher(pool,SimpleNamespace(handle=handle),is_navigation_update)
        await add(pool,event(1,'/menu'))
        await add(pool,event(2,MENU[1]))

        async def recovered():
            await dispatcher.schedule()
            return await pool.fetchval('SELECT done FROM inbox WHERE update_id=2')

        await until(recovered)
        assert attempts == [1,1,2]
    finally:
        await dispatcher.close()


async def test_poll_recovers_from_telegram_502_without_process_restart(env, monkeypatch):
    pool, *_ = env
    seen = []
    retries = []
    real_sleep = asyncio.sleep

    async def fake_sleep(delay):
        retries.append(delay)
        await real_sleep(0)

    async def updates(**kwargs):
        seen.append(kwargs['offset'])
        if len(seen)==1:
            raise TelegramServerError(GetUpdates(),'Bad Gateway')
        if len(seen)==2:
            raise TelegramRetryAfter(GetUpdates(),'Too many requests',3)
        return [event(10,'/menu')]

    async def enqueue(updates):
        for update in updates:
            await add(pool,update)
        assert retries == [1,3]
        raise asyncio.CancelledError

    monkeypatch.setattr('elevenbot.telegram.asyncio.sleep',fake_sleep)
    try:
        await receive_updates(pool,SimpleNamespace(enqueue_updates=enqueue),SimpleNamespace(get_updates=updates))
    except asyncio.CancelledError:
        pass
    assert len(seen)==3 and await pool.fetchval('SELECT count(*) FROM inbox')==1
