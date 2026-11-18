from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendDocument

from elevenbot import consent
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from test_admin_access import event
from test_ui import Bot


class DocumentTransport(Bot):
    def __init__(self):
        super().__init__()
        self.trace = []
        self.fail_privacy = False
        self.send_invoice = AsyncMock()

    async def send_document(self, chat, document):
        if self.fail_privacy and document.filename == 'privacy.md':
            raise TelegramNetworkError(SendDocument(chat_id=chat, document=document), 'timeout')
        result = await super().send_document(chat, document)
        self.trace.append(document.filename)
        return result

    async def send_message(self, chat, text, reply_markup=None):
        if hasattr(reply_markup, 'inline_keyboard'):
            for row in reply_markup.inline_keyboard:
                self.trace.extend(b.callback_data for b in row if b.text == 'Принять')
        return await super().send_message(chat, text, reply_markup)


@pytest.mark.parametrize('scenario', ['success', 'second_file_failed', 'version_changed'])
async def test_first_entry(env, monkeypatch, scenario):
    pool, cfg, _, _ = env
    bot = DocumentTransport()
    app = TelegramApp(pool, replace(cfg, mode='clodex', payments_enabled=True, payment_backend='stars'), bot)
    user = await app.svc.identity(101)
    docs = consent.documents()
    source = Mock(wraps=app.svc.get_consent_documents)
    accept = AsyncMock(wraps=app.svc.accept)
    monkeypatch.setattr(app.svc, 'get_consent_documents', source)
    monkeypatch.setattr(app.svc, 'accept', accept)
    seq = 0

    async def send(text=None, callback=None):
        nonlocal seq
        seq += 1
        await app.handle(event(seq, text, callback=callback, chat=101))

    async def agreed():
        return await pool.fetchval('SELECT terms_version FROM identities WHERE user_id=$1', user)

    bot.fail_privacy = scenario == 'second_file_failed'
    await send('/start')
    source.assert_called_once_with()
    if bot.fail_privacy:
        assert bot.trace == ['terms.md'] and await agreed() is None
        await send(callback='buy')
        bot.send_invoice.assert_not_awaited()
        assert not await pool.fetchval('SELECT count(*) FROM payments WHERE user_id=$1', user)
        accept.assert_not_awaited()
        bot.fail_privacy = False
        bot.trace.clear()
        await send('/start')
    terms, privacy, offer = bot.trace
    assert (terms, privacy) == ('terms.md', 'privacy.md') and offer.startswith('accept:')
    assert [f.data for f in bot.documents[-2:]] == [docs[k].encode() for k in ('terms','privacy')]
    if scenario == 'version_changed':
        monkeypatch.setattr(consent, 'CURRENT_VERSION', 'fixture-v2')
        await send(callback=offer)
        accept.assert_awaited_once_with(user, docs['version'])
        assert await agreed() is None
        assert bot.trace[-3:-1] == ['terms.md', 'privacy.md'] and bot.trace[-1] != offer
        offer = bot.trace[-1]
    await send(callback=offer)
    accept.assert_awaited_with(user, consent.CURRENT_VERSION)
    assert await agreed() == consent.CURRENT_VERSION
    assert 'Выберите агрегатор.' in bot.sent[-1][0]
    await send('/terms')
    await send('/privacy')
    assert [f.data for f in bot.documents[-2:]] == [docs[k].encode() for k in ('terms','privacy')]

    async with pool.acquire() as conn:
        await app.svc.movement(conn,user,'live','tg02-fixture-credit','pilot_grant',123,0)
    work = await app.svc.save_image_work(user, -501, 'fixture/image', 'fixture',
                                         SimpleNamespace(image=MOCK_IMAGE,filename='test.png'))
    calls = accept.await_count
    await send('/start')
    assert accept.await_count == calls and (await app.svc.wallet(user))['available'] == 123
    assert (await app.svc.image_work(user, work))['image'] == MOCK_IMAGE
