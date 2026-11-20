from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendDocument

from elevenbot.config import Config
from elevenbot.demo import DemoService
from elevenbot.demo_documents import DocumentDemoApp, FixtureDocuments
from elevenbot.interaction import MOCK_IMAGE
from test_admin_access import event
from test_ui import Bot


class DocumentsBot(Bot):
    def __init__(self):
        super().__init__()
        self.events = []
        self.fail_privacy = False

    async def send_document(self, chat, document):
        if self.fail_privacy and document.filename == 'privacy.md':
            raise TelegramNetworkError(SendDocument(chat_id=chat, document=document), 'fixture timeout')
        self.events.append((document.filename, document.data.decode()))
        return SimpleNamespace(message_id=len(self.events))

    async def send_message(self, chat, text, reply_markup=None):
        if hasattr(reply_markup, 'inline_keyboard'):
            for row in reply_markup.inline_keyboard:
                for button in row:
                    if button.text == 'Принять':
                        self.events.append(('accept', button.callback_data))
        return await super().send_message(chat, text, reply_markup)


@pytest.fixture
def prototype():
    return DocumentDemoApp(Config(mode='mock'), DocumentsBot(), DemoService(), FixtureDocuments())


async def test_delivered_pair_accept_menu_and_review(prototype):
    app = prototype
    await app.handle(event(1, '/start'))
    terms, privacy, button = app.bot.events
    bundle = app.documents.current()
    assert [terms[0], privacy[0], button[0]] == ['terms.md', 'privacy.md', 'accept']
    assert all('ТЕСТ' in data and bundle.id in data for _, data in (terms, privacy))
    assert not app.documents.receipts
    await app.handle(event(2, callback=button[1]))
    assert app.documents.receipts == {await app.svc.identity(100): bundle.id}
    assert 'Выберите агрегатор.' in app.bot.sent[-1][0]
    for n, command in enumerate(('/terms', '/privacy'), 3):
        await app.handle(event(n, command))
    assert app.bot.events[-2:] == [terms, privacy]


async def test_failed_second_file_retry_and_purchase_gate(prototype):
    app = prototype
    app.bot.fail_privacy = True
    await app.handle(event(1, '/start'))
    assert [name for name,_ in app.bot.events] == ['terms.md']
    assert '/start' in app.bot.sent[-1][0]
    for n, data in enumerate(('buy', 'accept', 'testdocs:' + app.documents.current().id), 2):
        await app.handle(event(n, callback=data))
        assert not app.documents.receipts and await app.svc.identity(100) not in app.offers
    assert not app.svc.users[await app.svc.identity(100)]['accepted']
    app.bot.fail_privacy = False
    await app.handle(event(5, '/start'))
    assert [name for name,_ in app.bot.events[1:]] == ['terms.md', 'privacy.md', 'accept']
    await app.handle(event(6, callback=app.bot.events[-1][1]))
    assert 'Выберите агрегатор.' in app.bot.sent[-1][0]


async def test_changed_bundle_preserves_account(prototype):
    app = prototype
    user = await app.svc.identity(100)
    await app.svc.accept(user)
    job = await app.svc.save_image_work(user, 100, 'fixture', 'old work',
                                       SimpleNamespace(image=MOCK_IMAGE, filename='old.png'))
    balance = await app.svc.wallet(user)
    await app.handle(event(1, '/start'))
    old = app.bot.events[-1][1]
    await app.handle(event(2, '/test_new_bundle'))
    await app.handle(event(3, callback=old))
    assert not app.documents.receipts
    assert [name for name,_ in app.bot.events[-3:]] == ['terms.md', 'privacy.md', 'accept']
    fresh = app.bot.events[-1][1]
    assert fresh != old
    await app.handle(event(4, callback=fresh))
    await app.handle(event(5, '/start'))
    assert 'Выберите агрегатор.' in app.bot.sent[-1][0]
    assert app.documents.receipts == {user: fresh.split(':')[1]}
    assert await app.svc.wallet(user) == balance
    assert (await app.svc.image_work(user, job))['image'] == MOCK_IMAGE
