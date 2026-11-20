"""TG-02 local demo. The fixture's identifiers and receipts live only in memory."""
from dataclasses import dataclass
from uuid import uuid4

from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile

from .demo import DemoApp
from .telegram import buttons


@dataclass(frozen=True)
class Bundle:
    id: str
    terms: bytes
    privacy: bytes


class FixtureDocuments:
    """Local stand-in for SL-01. Acceptance is conditional on the supplied ID."""

    def __init__(self):
        self.receipts = {}
        self.rotate()

    def rotate(self):
        id_ = uuid4().hex
        note = f'\n\nТестовый комплект {id_}. Только для проверки интерфейса.\n'
        self.bundle = Bundle(id_, ('# ТЕСТ — условия использования' + note).encode(),
                             ('# ТЕСТ — политика конфиденциальности' + note).encode())

    def current(self):
        return self.bundle

    def accepted(self, user):
        return self.receipts.get(user) == self.bundle.id

    def accept(self, user, shown_id):
        if shown_id != self.bundle.id:
            return False
        self.receipts[user] = shown_id
        return True


class DocumentDemoApp(DemoApp):
    def __init__(self, cfg, bot, service, documents):
        super().__init__(cfg, bot, service)
        self.documents = documents
        self.offers = {}

    async def present(self, user, chat):
        self.offers.pop(user, None)
        bundle = self.documents.current()
        try:
            for filename, content in [('terms.md', bundle.terms), ('privacy.md', bundle.privacy)]:
                await self.bot.send_document(chat, BufferedInputFile(content, filename=filename))
        except TelegramAPIError:
            await self.say(chat, 'Доставка комплекта не подтверждена. Повторите /start.')
            return
        await self.say(chat, 'Принять показанные тестовые документы?',
                       buttons([[('Принять', 'testdocs:' + bundle.id)]]))
        self.offers[user] = bundle.id

    async def handle_chat(self, update, ext, *, from_inbox):
        callback = update.callback_query
        message = callback.message if callback else update.message
        if not message or message.chat.type != 'private' or message.chat.id != ext:
            return
        user = await self.svc.identity(ext)
        words = (update.message.text or '').split() if update.message else []
        command = words[0].partition('@')[0].lower() if words else ''
        data = (callback.data or '') if callback else ''
        if command == '/test_new_bundle':
            self.documents.rotate()
            await self.say(ext, 'Тестовый комплект сменился.')
        elif command in ('/terms', '/privacy'):
            bundle = self.documents.current()
            name = command[1:]
            await self.bot.send_document(ext, BufferedInputFile(getattr(bundle, name), filename=name + '.md'))
        elif data.startswith('testdocs:'):
            await self.bot.answer_callback_query(callback.id)
            shown = data.partition(':')[2]
            if self.offers.get(user) == shown and self.documents.accept(user, shown):
                self.offers.pop(user)
                await self.svc.accept(user)
                await self.open_aggregators(user, ext)
            elif self.documents.accepted(user):
                await self.open_aggregators(user, ext)
            elif user not in self.offers:
                await self.say(ext, 'Для просмотра документов откройте /start.')
            else:
                await self.say(ext, 'Подтвердите актуальный комплект.')
                await self.present(user, ext)
        elif command == '/start':
            if self.documents.accepted(user):
                await self.open_aggregators(user, ext)
            else:
                await self.present(user, ext)
        elif not self.documents.accepted(user) or data == 'accept':
            if callback:
                await self.bot.answer_callback_query(callback.id)
            await self.say(ext, 'Для просмотра документов откройте /start.')
        else:
            await super().handle_chat(update, ext, from_inbox=from_inbox)
