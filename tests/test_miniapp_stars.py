from dataclasses import replace
from unittest.mock import AsyncMock

from aiogram.types import Update
from aiohttp.test_utils import TestClient, TestServer

from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import account_db, signed
from test_admin_access import event
from test_ui import Bot


async def test_stars_invoice_close_then_confirm(account_db):
    pool, defaults = account_db
    cfg = replace(defaults, mode='clodex', payments_enabled=True, payment_backend='stars')
    bot = Bot()
    bot.create_invoice_link = AsyncMock(side_effect=['https://t.me/$first', 'https://t.me/$second'])
    app = TelegramApp(pool, cfg, bot)
    try:
        async with TestClient(TestServer(create_app(pool, cfg, view=app))) as client:
            async def login(chat):
                user = await app.svc.identity(chat)
                await app.svc.accept(user)
                response = await client.post('/api/v1/session', json={'initData': signed(cfg.token, chat)})
                assert response.status == 200
                return {'Authorization': 'Bearer ' + (await response.json())['token']}

            headers = await login(101)
            other = await login(100)

            async def invoice():
                response = await client.post('/api/v1/stars/invoices', headers=headers)
                assert response.status == 201
                result = await response.json()
                sent = bot.create_invoice_link.await_args.kwargs
                assert sent['payload'] == result['id'] and sent['currency'] == 'XTR'
                assert [p.amount for p in sent['prices']] == [100]
                return result

            async def screen(available, expected):
                wallet = await (await client.get('/api/v1/wallet', headers=headers)).json()
                assert wallet == {'available': str(available), 'reserved': '0'}
                history = await (await client.get('/api/v1/stars/payments', headers=headers)).json()
                assert [(p['id'], p['status']) for p in history['payments']] == expected
                assert history['checkout_enabled'] and not history['has_more']

            assert (await client.post('/api/v1/stars/invoices')).status == 401
            first = await invoice()
            assert first['url'] == 'https://t.me/$first'
            pending = [(first['id'], 'pending')]
            # Closing an invoice only refreshes server state, including on cancellation.
            await screen(0, pending)
            second = await invoice()
            assert second['url'] == 'https://t.me/$second' and second['id'] != first['id']
            actor = {'id': 101, 'is_bot': False, 'first_name': 'Fixture'}
            fields = dict(currency='XTR', total_amount=100, invoice_payload=second['id'])
            await app.handle(Update.model_validate({'update_id': 301, 'pre_checkout_query': {
                'from': actor, 'id': 'fixture-check', **fields}}))
            assert bot.answers[-1]['ok']
            await screen(0, [(second['id'], 'pending'), *pending])
            assert await pool.fetchval("SELECT count(*) FROM ledger WHERE kind='payment'") == 0

            for n in (302, 303):
                await app.handle(Update.model_validate({'update_id': n, 'message': {
                    'message_id': n, 'date': 1700000000, 'chat': {'id': 101, 'type': 'private'},
                    'from': actor, 'successful_payment': dict(fields, telegram_payment_charge_id='stars-test',
                                                              provider_payment_charge_id='')}}))
                await screen(10000, [(second['id'], 'succeeded'), *pending])
            rows = await pool.fetch("SELECT payment_id, da, dr FROM ledger WHERE kind='payment'")
            entry, = rows
            assert (str(entry['payment_id']), entry['da'], entry['dr']) == (second['id'], 10000, 0)
            await app.handle(event(304, '💳 Баланс', chat=101))
            assert any('Кредиты: 10000' in msg for msg, _ in bot.sent)
            history = await (await client.get('/api/v1/stars/payments', headers=other)).json()
            assert history['payments'] == []
            await pool.execute('UPDATE settings SET halted=true WHERE id=1')
            assert (await client.post('/api/v1/stars/invoices', headers=headers)).status == 403
            assert bot.create_invoice_link.await_count == 2
    finally:
        await app.topups.client.close()
