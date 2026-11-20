from dataclasses import replace
from itertools import count

import httpx
from aiohttp.test_utils import TestClient, TestServer

from elevenbot.pricing import Request
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed
from test_admin_access import event
from test_provider_extensibility import app_with_fixture
from test_ui import Bot


async def test_wallet_profile_during_and_after_generation(env, confirmed_credit):
    pool, cfg, _, owner = env
    cfg = replace(cfg, token='wallet-profile-test')
    ids = count(100)
    bot = Bot()
    model = 'fixture/chat'
    posts = []

    async def read_profile(chat, user, totals, expected, excluded):
        await app.handle(event(next(ids), '💳 Баланс', chat=chat))
        text, markup = bot.sent[-1]
        assert f'Личный кабинет · Telegram ID {chat}' in text
        balance = await app.svc.wallet(user)
        assert (balance['available'], balance['reserved']) == totals
        assert f"Кредиты: {totals[0]}\nЗарезервировано: {totals[1]}" in text
        response = await client.get('/api/v1/wallet', headers=headers[chat])
        assert response.status == 200
        assert await response.json() == dict(available=str(totals[0]), reserved=str(totals[1]))
        routes = {b.text: b.callback_data for row in markup.inline_keyboard for b in row}
        await app.handle(event(next(ids), callback=routes['Мои платежи'], chat=chat))
        assert f'{str(orders[chat])[:8]} · 100 XTR · Оплачено' in bot.sent[-1][0]
        for other_chat, order in orders.items():
            if other_chat != chat:
                assert str(order)[:8] not in bot.sent[-1][0]
        await app.handle(event(next(ids), callback=routes['История операций'], chat=chat))
        history = bot.sent[-1][0]
        for label in expected:
            assert history.count(label) == 1
        for label in excluded:
            assert label not in history
        return history

    async def provider(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'amount': 60})
        posts.append(request.url.path)
        await read_profile(100, owner, (40, 60), [credit, hold], [charge])
        return httpx.Response(200, json={'answer':'fixture'})

    credit = 'Пополнение: 100'
    hold = 'В резерв под задание: 60'
    charge = 'Списано из резерва за задание: 60'
    async with httpx.AsyncClient(base_url='https://fixture.invalid', transport=httpx.MockTransport(provider)) as http:
        app = app_with_fixture(pool, cfg, bot, http)
        other = await app.svc.identity(101)
        await app.svc.accept(other)
        _, first_order = await confirmed_credit(pool, cfg, owner, 100)
        _, second_order = await confirmed_credit(pool, cfg, other, 17, charge='tg03-second-account')
        orders = {100:first_order, 101:second_order}
        await app.pricing.set_rate(owner, 100, 'fixture_token', '1', provider='fixture')
        await pool.execute("INSERT INTO approved_models VALUES('fixture',$1,'chat','Model')", model)
        quote = await app.pricing.quote(owner, Request('fixture',model,'chat','Model','Prompt'))
        async with TestClient(TestServer(create_app(pool, app.cfg))) as client:
            headers = {}
            for chat in (100, 101):
                login = await client.post('/api/v1/session', json={'initData':signed(cfg.token,chat)})
                assert login.status == 200
                headers[chat] = {'Authorization':'Bearer ' + (await login.json())['token']}
            await read_profile(100, owner, (100, 0), [credit], [hold, charge])
            await app.handle(event(next(ids), callback=f'amconfirm:{quote.id}'))
            result = await read_profile(100, owner, (40, 0), [credit, hold, charge], ['Пополнение: 17'])
            assert result.count(f'задание {str(quote.id)[:8]}') == 2
            await read_profile(101, other, (17, 0), ['Пополнение: 17'], [credit, hold, charge])
            assert posts == ['/generate']
