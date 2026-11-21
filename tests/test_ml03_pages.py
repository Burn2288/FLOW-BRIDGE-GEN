from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from elevenbot.telegram import TelegramApp
from test_ui import Bot


async def test_telegram_history_has_five_rows_per_page(env):
    pool, cfg, _, user = env
    bot = Bot()
    app = TelegramApp(pool, cfg, bot)
    rows = [dict(id=str(i), kind='image', price=i, status='succeeded',
                 created_at=datetime.now(timezone.utc), file_available=True) for i in range(7)]
    app.svc.history = AsyncMock(side_effect=lambda owner, offset: rows[offset:offset + 10])
    try:
        await app.history(user, 100, 0)
        text, keyboard = bot.sent[-1]
        assert text.count(' · Изображение · ') == 5
        assert any(b.text == 'Далее' for row in keyboard.inline_keyboard for b in row)
        await app.history(user, 100, 1)
        text, keyboard = bot.sent[-1]
        assert text.count(' · Изображение · ') == 2
        assert '6.' in text and '7.' in text
        assert not any(b.text == 'Далее' for row in keyboard.inline_keyboard for b in row)
    finally:
        await app.topups.client.close()
