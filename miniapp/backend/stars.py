"""Telegram Stars invoices for the authenticated Mini App account."""

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import LabeledPrice
from aiohttp import web

from elevenbot.core import Rejected


def add_stars_routes(app, service, account, cfg, bot):
    async def payments(request):
        user = await account(request)
        try:
            page = int(request.query.get('page', '0'))
            if not 0 <= page <= 10000:
                raise ValueError
        except ValueError:
            raise web.HTTPBadRequest() from None
        rows = await service.pool.fetch(
            """SELECT id, amount, currency, credits, status, created_at FROM payments
               WHERE user_id=$1 AND provider='telegram'
               ORDER BY created_at DESC, id DESC LIMIT 11 OFFSET $2""", user, page * 10)
        enabled = cfg.payments_enabled and cfg.payment_backend == 'stars' and cfg.mode != 'mock'
        return web.json_response({
            'checkout_enabled': enabled and not await service.pool.fetchval('SELECT halted FROM settings WHERE id=1'),
            'has_more': len(rows) > 10,
            'payments': [dict(id=str(r['id']), amount=r['amount'], currency=r['currency'],
                              credits=r['credits'], status=r['status'], created_at=r['created_at'].isoformat())
                         for r in rows[:10]],
        })

    async def invoice(request):
        user = await account(request)
        try:
            order = await service.order(user)
        except Rejected as exc:
            raise web.HTTPForbidden(text=str(exc)) from None
        row = await service.pool.fetchrow(
            'SELECT amount, currency, credits FROM payments WHERE id=$1 AND user_id=$2', order, user)
        label = f"{row['credits']:,} кредитов".replace(',', ' ')
        fields = dict(title='Пакет кредитов', description=f'{label} DarkFlow | Gen',
                      payload=str(order), provider_token='', currency=row['currency'],
                      prices=[LabeledPrice(label=label, amount=row['amount'])])
        try:
            if bot is None:
                async with Bot(cfg.token) as client:
                    url = await client.create_invoice_link(**fields)
            else:
                url = await bot.create_invoice_link(**fields)
        except TelegramAPIError:
            raise web.HTTPBadGateway(text='Не удалось открыть счёт Telegram.') from None
        return web.json_response({'id': str(order), 'url': url}, status=201)

    app.router.add_get('/api/v1/stars/payments', payments)
    app.router.add_post('/api/v1/stars/invoices', invoice)
