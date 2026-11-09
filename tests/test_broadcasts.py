from dataclasses import replace

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.methods import SendMessage
from aiogram.types import MessageEntity, PhotoSize

from elevenbot.aggregate import make_snapshot
from elevenbot.anymodel import model_store
from elevenbot.broadcasts import Broadcasts, BroadcastWorker, report_text
from elevenbot.discovery import SnapshotStore
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
    await send('/admin')
    await send(cfg.admin_password)
    labels = list(routes(await panel()))
    assert labels.index('📣 Рассылки') == labels.index('Тарифы моделей') + 1
    await send(callback=routes(await panel())['📣 Рассылки'])
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
    await send(callback=routes(await panel())['Только мне'])
    assert 'Получателей: 1' in (await panel())[1]
    confirm = routes(await panel())['Разослать · 1 получ.']
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
    await send(callback='brlist', chat=admin_chat+1)
    assert bot.answers[-1][1]['text'] == 'Админ-доступ закрыт.'
    print('BROADCAST_UI user_hidden=true admin_position=true back=true logout_denied=true '
          'photo_caption_entities=true one_delivery=true navigation_preserved=true')


async def test_broadcast_bulk_snapshot_preferences_restart_and_stop(env):
    pool, cfg, svc, _ = env
    queue = Broadcasts(pool)
    bot = BroadcastTransport(pool)
    app = TelegramApp(pool, cfg, bot)
    for chat in range(100, 109):
        user = await svc.identity(chat)
        if chat != 108:
            await svc.accept(user)
        if chat != 107:
            await queue.observe_private(chat)
    await app.handle(event(1, MENU[3], chat=106))
    state = await app.navigation.read(106)
    await app.handle(event(2, chat=106, callback=routes(bot.messages[state.active_id])['Настройки рассылок']))
    await app.handle(event(3, chat=106, callback='broff'))
    assert await queue.preference(106) is True
    await app.handle(event(4, chat=106, callback='bron'))
    assert await queue.preference(106) is False
    await app.handle(event(5, chat=106, callback='broff'))
    assert await queue.preference(106) is True

    row = await queue.draft(100)
    id = row['id']
    row = await queue.save_post(100, id, row['revision'], event(6, 'Ссылка').message)
    row = await queue.select_audience(100, id, row['revision'], 'all')
    assert row['expected_count'] == 6
    await queue.confirm(100, id, row['revision'])
    await queue.confirm(100, id, row['revision'])
    assert await queue.counts(id) == {'pending':6}

    # Persisted in-flight send with unknown response is never retried after restart.
    assert (await queue.claim())[1] == 100
    restarted = Broadcasts(pool)
    await restarted.recover()
    worker = BroadcastWorker(restarted, bot, buttons)
    await queue.preference(101, True)
    claim = await restarted.claim()
    assert claim[1:] == (101, False)
    await worker.deliver(claim)
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
    await queue.stop(100, id)
    assert await restarted.claim() is None
    assert [post[0] for post in bot.posts] == [102,102,103,104]
    counts = {'unknown':2,'opted_out':1,'sent':1,'unavailable':1,'stopped':1}
    assert await restarted.counts(id) == counts
    assert 'Отправлено 1 из 6 · 1 недоступны · 0 ошибки' in report_text(counts)
