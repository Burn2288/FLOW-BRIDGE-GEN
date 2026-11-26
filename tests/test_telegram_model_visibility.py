from uuid import uuid4

from elevenbot.model_visibility import confirm
from elevenbot.telegram import TelegramApp
from test_admin_access import event
from test_ui import Bot


async def test_telegram_model_visibility_uses_preview_cas_and_current_authority(env):
    pool, cfg, _, actor = env
    bot = Bot()
    app = TelegramApp(pool, cfg, bot)
    key = ('clodex', 'flux-schnell', 'images.generate')
    command = '/model_visibility ' + ' '.join(key)

    async def visibility():
        return await pool.fetchval(
            'SELECT visibility FROM approved_models WHERE (provider,model_id,operation)=($1,$2,$3)', *key)

    async def preview(number, action):
        await app.handle(event(number, f'{command} {action}'))
        text, markup = bot.sent[-1]
        assert text.startswith('Предпросмотр')
        assert markup.inline_keyboard[0][0].text == 'Подтвердить'
        return markup.inline_keyboard[0][0].callback_data, (await app.navigation.read(100)).active_id

    async def click(number, button):
        route, source = button
        await app.handle(event(number, callback=route, source_message_id=source))

    async def role(value):
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,$2,'synthetic Telegram settings check')
        """, actor, value)

    await app.handle(event(700, command + ' HIDDEN'))
    assert 'Управление видимостью недоступно' in bot.sent[-1][0]
    await role('SETTINGS_OPERATOR')
    stale = await preview(701, 'HIDDEN')
    assert await visibility() == 'VISIBLE'
    async with pool.acquire() as conn, conn.transaction():
        published = await confirm(conn, actor, *key, 'HIDDEN', 0, uuid4())
    await click(702, stale)
    assert 'Модель изменилась' in bot.sent[-1][0]

    rollback = await preview(703, 'rollback')
    assert 'HIDDEN → VISIBLE' in bot.sent[-1][0]
    await click(704, rollback)
    assert 'Видимость сохранена: VISIBLE' in bot.sent[-1][0]
    assert await visibility() == 'VISIBLE'
    assert await pool.fetchval(
        'SELECT rollback_of FROM model_visibility_events ORDER BY version DESC LIMIT 1') == published['version']
    await click(705, rollback)
    pending = await preview(706, 'HIDDEN')
    await role(None)
    await click(707, pending)
    assert 'Управление видимостью недоступно' in bot.sent[-1][0]
    assert await visibility() == 'VISIBLE'
    assert await pool.fetchval('SELECT count(*) FROM model_visibility_events') == 2
