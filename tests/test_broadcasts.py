import asyncio
import os
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.methods import SendMessage
from aiogram.types import MessageEntity, PhotoSize

from elevenbot.aggregate import make_snapshot
from elevenbot.anymodel import model_store
from elevenbot.broadcasts import CAPTION_MEDIA, MEDIA, VISUAL_MEDIA, Broadcasts, BroadcastWorker, report_text, send_post
from elevenbot.discovery import SnapshotStore
from elevenbot.pricing import NoProviderPrice, Pricing, Request
from elevenbot.telegram import MENU, TelegramApp, buttons
from test_admin_access import event
from test_navigation import Transport


@pytest.fixture
def admin_already_signed_in():
    pass


class BroadcastTransport(Transport):
    def __init__(self, pool):
        super().__init__(pool)
        self.posts = []
        self.delivery_errors = {}

    async def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))

    async def send_message(self, chat, text, reply_markup=None, *, entities=None):
        if entities is not None:
            return await self.post(chat, 'text', text, None, entities, reply_markup)
        return await super().send_message(chat, text, reply_markup)

    async def send_photo(self, chat, photo, *, caption, reply_markup, caption_entities=None):
        if caption_entities is not None:
            return await self.post(chat, 'photo', caption, photo, caption_entities, reply_markup)
        return await super().send_photo(chat, photo, caption=caption, reply_markup=reply_markup)

    async def post(self, chat, kind, text, photo, entities, markup):
        self.posts.append((chat, kind, text, photo, entities, markup))
        if error := self.delivery_errors.pop(chat, None):
            raise error
        return await self.send(kind, text, markup)


def routes(screen):
    return {button.text: button.callback_data for row in screen[2].inline_keyboard for button in row}


async def test_broadcast_ui_self_preview_delivery_and_permissions(env, tmp_path):
    pool, cfg, _, _ = env
    cfg = replace(cfg, access_mode='private', admin_ids=(100,), admin_password='fixture-password',
                  anymodel_test_enabled=True, catalogue_path=str(tmp_path/'catalogue.json'))
    SnapshotStore(cfg.catalogue_path).write(make_snapshot([], [], [{'provider':'clodex'}]))
    model_store(cfg).write(make_snapshot([], [], [{'provider':'anymodel'}]))
    await exercise_broadcast_ui(pool, cfg)


async def exercise_broadcast_ui(pool, cfg, admin_chat=100):
    bot = BroadcastTransport(pool)
    app = TelegramApp(pool, cfg, bot)
    queue = app.broadcasts.queue
    n = 0

    async def send(text=None, callback=None, chat=admin_chat):
        nonlocal n
        n += 1
        await app.handle(event(n, text, chat=chat, callback=callback))

    async def panel(chat=admin_chat):
        return bot.messages[(await app.navigation.read(chat)).active_id]

    await send('/menu')
    assert '📣 Рассылки' not in routes(await panel())
    await send(MENU[3])
    assert 'Настройки рассылок' not in routes(await panel())
    await send('/admin')
    await send(cfg.admin_password)
    labels = list(routes(await panel()))
    assert labels.index('📣 Рассылки') == labels.index('Тарифы моделей') + 1
    await send(callback=routes(await panel())['📣 Рассылки'])
    assert (await panel())[1] == 'Системные уведомления'
    assert list(routes(await panel())) == ['Создать рассылку', '← Назад']
    await send(callback=routes(await panel())['← Назад'])
    assert '📣 Рассылки' in routes(await panel())
    await send(callback=routes(await panel())['📣 Рассылки'])
    await send(callback=routes(await panel())['Создать рассылку'])

    n += 1
    update = event(n, chat=admin_chat)
    caption = '🔮 Тест ссылки'
    entities = [MessageEntity(type='text_link', offset=3, length=4, url='https://example.org')]
    photo = PhotoSize(file_id='photo-fixture', file_unique_id='fixture', width=64, height=64)
    message = update.message.model_copy(update={'caption':caption, 'photo':[photo], 'caption_entities':entities})
    update = update.model_copy(update={'message':message})
    await app.handle(update)
    preview_id = bot.next_id
    preview = bot.messages[preview_id]
    assert preview[:2] == ('photo', caption)
    assert list(routes(preview)) == ['Заменить пост', 'Выбрать получателей', 'Отменить']
    await send(callback=routes(preview)['Выбрать получателей'])
    assert (await app.navigation.read(admin_chat)).active_id > preview_id
    assert bot.messages[preview_id] == preview
    assert list(routes(await panel())) == ['Только мне', 'Всем пользователям бота', 'Отменить']
    await send(callback=routes(await panel())['Только мне'])
    assert 'Получателей: 1' in (await panel())[1]
    confirm = routes(await panel())['Разослать 1 пользователю']
    await send(callback=confirm)
    await send(callback=confirm)

    worker = BroadcastWorker(queue, bot, buttons)
    claim = await queue.claim()
    await worker.deliver(claim)
    assert await queue.claim() is None
    broadcast = claim[0]['id']
    assert await queue.counts(broadcast) == {'sent':1}
    delivery = bot.next_id
    assert bot.posts[0][:5] == bot.posts[1][:5] == (admin_chat, 'photo', caption, 'photo-fixture', entities)
    assert bot.posts[1][5] is None
    assert await pool.fetchval('SELECT message_id FROM telegram_broadcast_deliveries WHERE broadcast_id=$1',
                               broadcast) == delivery
    await worker.report(await queue.next_report())
    assert any('Отправлено 1 из 1' in screen[1] for screen in bot.messages.values())
    for label in (MENU[0], MENU[1], '/menu'):
        await send(label)
        assert bot.messages[delivery] == ('photo', caption, None)
    await send('/admin_logout')
    assert '📣 Рассылки' not in routes(await panel())
    await send(callback='brlist')
    assert bot.answers[-1][1]['text'] == 'Войдите через /admin.'
    await send(callback=confirm)
    assert bot.answers[-1][1]['text'] == 'Войдите через /admin.'
    await send(callback=f'brstop:{broadcast}')
    assert bot.answers[-1][1]['text'] == 'Войдите через /admin.'
    await send(callback='brlist', chat=admin_chat+1)
    assert bot.answers[-1][1]['text'] == 'Админ-доступ закрыт.'
    print('BROADCAST_UI user_hidden=true admin_position=true back=true logout_denied=true '
          'photo_caption_entities=true one_delivery=true navigation_preserved=true')


async def test_broadcast_bulk_snapshot_restart_and_stop(env):
    pool, _, svc, _ = env
    queue = Broadcasts(pool)
    bot = BroadcastTransport(pool)
    for chat in range(100, 109):
        user = await svc.identity(chat)
        if chat != 108:
            await svc.accept(user)
        if chat != 107:
            await queue.observe_private(chat)

    row = await queue.draft(100)
    id = row['id']
    row = await queue.save_post(100, id, row['revision'], event(6, 'Ссылка').message)
    row = await queue.select_audience(100, id, row['revision'], 'all')
    assert row['expected_count'] == 7
    await queue.confirm(100, id, row['revision'])
    await queue.confirm(100, id, row['revision'])
    assert await queue.counts(id) == {'pending':7}
    recipients = await pool.fetch("""
        SELECT chat_id FROM telegram_broadcast_deliveries WHERE broadcast_id=$1 ORDER BY chat_id
        """, id)
    assert [recipient['chat_id'] for recipient in recipients] == list(range(100, 107))
    await svc.accept(await svc.identity(109))
    await queue.observe_private(109)
    assert await queue.counts(id) == {'pending':7}

    await BroadcastWorker(queue, bot, buttons).deliver(await queue.claim())
    # Neither a known success nor an in-flight send with an unknown response is retried.
    assert (await queue.claim())[1] == 101
    restarted = Broadcasts(pool)
    await restarted.recover()
    worker = BroadcastWorker(restarted, bot, buttons)
    method = SendMessage(chat_id=102,text='fixture')
    bot.delivery_errors[102] = TelegramRetryAfter(method, 'rate limit', 2)
    await worker.deliver(await restarted.claim())
    assert await restarted.claim() is None
    assert await pool.fetchval('SELECT resume_at>now() FROM telegram_broadcast_throttle')
    await pool.execute('UPDATE telegram_broadcast_throttle SET resume_at=now()')
    await pool.execute('UPDATE telegram_broadcast_deliveries SET retry_at=now() WHERE chat_id=102')
    await worker.deliver(await restarted.claim())
    bot.delivery_errors[103] = TelegramForbiddenError(method, 'blocked')
    await worker.deliver(await restarted.claim())
    bot.delivery_errors[104] = TelegramNetworkError(method, 'timeout')
    await worker.deliver(await restarted.claim())
    bot.delivery_errors[105] = TelegramBadRequest(method, 'fixture rejected')
    await worker.deliver(await restarted.claim())
    await queue.stop(100, id)
    assert await restarted.claim() is None
    assert [post[0] for post in bot.posts] == [100,102,102,103,104,105]
    counts = {'unknown':2,'sent':2,'unavailable':1,'error':1,'stopped':1}
    assert await restarted.counts(id) == counts
    assert 'Отправлено 2 из 7 · Недоступные чаты: 1 · Ошибки: 1' in report_text(counts)
    print(report_text(counts), flush=True)


@pytest.mark.parametrize('kind', MEDIA)
async def test_broadcast_media_survives_restart_and_keeps_caption(env, kind):
    pool, _, _, _ = env
    queue = Broadcasts(pool)
    await queue.observe_private(100)
    draft = await queue.draft(100)
    file = SimpleNamespace(file_id='telegram-file')
    values = {kind: [file] if kind == 'photo' else file}
    if kind == 'animation':
        values['document'] = SimpleNamespace(file_id='fallback-document')
    if kind in CAPTION_MEDIA:
        values.update(caption='Ссылка', caption_entities=[
            MessageEntity(type='text_link', offset=0, length=6, url='https://example.org'),
        ])
    if kind in VISUAL_MEDIA:
        values.update(has_media_spoiler=True, show_caption_above_media=True)
    message = event(1).message.model_copy(update=values)
    post = await queue.save_post(100, draft['id'], draft['revision'], message)
    send = AsyncMock(return_value=SimpleNamespace(message_id=1234))
    bot = SimpleNamespace(**{f'send_{kind}': send})
    markup = buttons([[('Выбрать получателей', 'test')]])
    await send_post(bot, 100, post, markup)
    preview = send.await_args
    assert preview.args == (100, 'telegram-file')
    assert preview.kwargs['reply_markup'] == markup
    if kind in CAPTION_MEDIA:
        assert preview.kwargs['caption'] == message.caption
        assert preview.kwargs['caption_entities'] == message.caption_entities
    else:
        assert set(preview.kwargs) == {'reply_markup'}
    if kind in VISUAL_MEDIA:
        assert preview.kwargs['has_spoiler'] and preview.kwargs['show_caption_above_media']
    chosen = await queue.select_audience(100, draft['id'], post['revision'], 'self')
    await queue.confirm(100, draft['id'], chosen['revision'])
    restarted = Broadcasts(pool)
    await restarted.recover()
    await BroadcastWorker(restarted, bot, buttons).deliver(await restarted.claim())
    assert await restarted.claim() is None
    assert send.await_count == 2
    assert send.await_args.args == preview.args
    assert send.await_args.kwargs == {**preview.kwargs, 'reply_markup': None}
    assert await restarted.counts(draft['id']) == {'sent': 1}


@pytest.mark.parametrize('sending', [False, True], ids=['idle', 'sending'])
async def test_broadcast_loop_does_not_block_pricing(env, sending):
    pool, cfg, _, user = env
    cfg = replace(cfg, admin_ids=(100,), interaction_limit=10)
    worker_ready = asyncio.Event()
    competitor_tried = asyncio.Event()
    send_started = asyncio.Event()
    allow_send = asyncio.Event()
    delivered = asyncio.Event()
    calls = []

    class Queue(Broadcasts):
        def __init__(self, pool, ready):
            super().__init__(pool)
            self.ready = ready

        async def claim(self):
            claim = await super().claim()
            self.ready.set()
            return claim

        async def complete(self, *args, **kwargs):
            await super().complete(*args, **kwargs)
            delivered.set()

    async def send(chat, body, **kwargs):
        calls.append(('first', chat, body))
        send_started.set()
        await allow_send.wait()
        return SimpleNamespace(message_id=1001)

    async def duplicate(chat, body, **kwargs):
        calls.append(('second', chat, body))
        return SimpleNamespace(message_id=1002)

    def observe_query(query):
        if 'pg_try_advisory_lock' in query.query:
            competitor_tried.set()

    async def observe_connection(conn):
        conn.add_query_logger(observe_query)

    async def held_lock():
        # Observe both the historical key and the new two-integer key so the
        # old implementation fails on pricing, rather than on test setup.
        return await pricing_pool.fetchrow("""
            SELECT pid,classid,objid,objsubid FROM pg_locks
            WHERE locktype='advisory' AND granted AND pid<>pg_backend_pid()
              AND database=(SELECT oid FROM pg_database WHERE datname=current_database())
              AND ((classid=0 AND objid=921189 AND objsubid=1)
                OR (classid=921190 AND objid=0 AND objsubid=2))
            """)

    async def bounded(operation, awaitable):
        try:
            return await asyncio.wait_for(awaitable, timeout=2)
        except TimeoutError:
            raise AssertionError(f'{operation} timed out while BroadcastWorker held its advisory lock') from None

    queue = Queue(pool, worker_ready)
    schema = await pool.fetchval('SELECT current_schema()')
    async with asyncpg.create_pool(os.environ['TEST_DATABASE_URL'], min_size=1, max_size=4,
                                   server_settings={'search_path': schema}, init=observe_connection) as pricing_pool:
        pricing = Pricing(pricing_pool, cfg, {'fixture':SimpleNamespace(cost=AsyncMock(side_effect=NoProviderPrice))})

        async def tariff(model, amount):
            await pricing.set_tariff(user,100,'fixture',model,'chat',{},basis='request',
                                     unit='darkflow_token',amount=amount,evidence='fixture-rate')

        async def prepare(conn, quote):
            pass

        await tariff('fixture/quoted','100')
        quote = await pricing.quote(user, Request('fixture','fixture/quoted','chat','Fixture','prompt'))
        if sending:
            await queue.observe_private(100)
            draft = await queue.draft(100)
            post = await queue.save_post(100,draft['id'],draft['revision'],event(1,'Fixture post').message)
            chosen = await queue.select_audience(100,draft['id'],post['revision'],'self')
            await queue.confirm(100,draft['id'],chosen['revision'])

        first = asyncio.create_task(BroadcastWorker(queue,SimpleNamespace(send_message=send),buttons).loop())
        second = None
        try:
            await asyncio.wait_for((send_started if sending else worker_ready).wait(), timeout=5)
            lock = await held_lock()
            assert lock is not None
            outcomes = await asyncio.gather(
                bounded('set_tariff',tariff('fixture/changed','250')),
                bounded('confirm_quote',pricing.confirm(user,quote.id,42,prepare)),
                return_exceptions=True,
            )
            errors = [str(outcome) for outcome in outcomes if isinstance(outcome,Exception)]
            assert not errors, '\n'.join(errors)
            assert outcomes[1][1] is True
            assert await pricing_pool.fetchval("SELECT amount FROM task_manual_tariffs WHERE model_id='fixture/changed'")==250
            assert await held_lock()==lock
            if sending:
                assert await queue.counts(draft['id'])=={'sending':1}
                contender_ready = asyncio.Event()
                contender = Queue(pricing_pool, contender_ready)
                second = asyncio.create_task(BroadcastWorker(contender,SimpleNamespace(send_message=duplicate),buttons).loop())
                await asyncio.wait_for(competitor_tried.wait(), timeout=5)
                assert not contender_ready.is_set()
                assert await queue.counts(draft['id'])=={'sending':1}
                allow_send.set()
                await asyncio.wait_for(delivered.wait(), timeout=5)
                first.cancel()
                await asyncio.gather(first, return_exceptions=True)
                await asyncio.wait_for(contender_ready.wait(), timeout=5)
                assert calls==[('first',100,'Fixture post')]
                assert await queue.counts(draft['id'])=={'sent':1}
            else:
                assert not calls
            print(f'BROADCAST_LOCK phase={"sending" if sending else "idle"} '
                  f'tariff=completed confirm=accepted posts={len(calls)}',flush=True)
        finally:
            workers = [task for task in (first, second) if task is not None]
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers,return_exceptions=True)
        assert await held_lock() is None
