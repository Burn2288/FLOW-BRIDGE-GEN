"""Authenticated Platega callback listener, behind an HTTPS reverse proxy."""

import asyncio
import json
import os

from aiohttp import web

from .core import Rejected, uid
from .platega import PlategaPayments, PaymentInvalid, PaymentUnknown
from .topups import CheckoutClient, Topups, client_config


def create_app(payments):
    app=web.Application(client_max_size=65536)
    async def callback(request):
        if not payments.client.authenticated(request.headers):
            return web.Response(status=401)
        try:
            await payments.callback(request.headers,await request.read())
        except PermissionError:
            return web.Response(status=401)
        except PaymentInvalid:
            return web.Response(status=400)
        except PaymentUnknown:
            return web.Response(status=503)
        except web.HTTPRequestEntityTooLarge:
            raise
        except Exception:
            return web.Response(status=503)
        return web.Response(status=200)
    app.router.add_post('/payments/platega/callback',callback)
    return app


class PaymentRouter:
    def __init__(self,pool,cfg,client):
        self.pool,self.client=pool,client
        self.topups=Topups(pool,cfg,client)
        self.legacy=PlategaPayments(pool,cfg,client)

    async def callback(self,headers,body):
        if not self.client.authenticated(headers):
            raise PermissionError('Unauthorized')
        try:
            event=json.loads(body)
            remote=uid(event['id'])
        except (ValueError,TypeError,KeyError,Rejected):
            raise PaymentInvalid('Malformed callback') from None
        topup=await self.pool.fetchval("""SELECT EXISTS(
            SELECT 1 FROM payments p JOIN topup_orders t ON t.payment_id=p.id
            WHERE p.remote_id=$1 OR p.id::text=$2)""",remote,event.get('payload',''))
        return await (self.topups if topup else self.legacy).callback(headers,body)


async def serve(pool,cfg):
    if cfg.topup_mode!='live':
        raise ValueError('External webhook requires verified live configuration')
    client=CheckoutClient(client_config(cfg))
    runner=web.AppRunner(create_app(PaymentRouter(pool,cfg,client)),access_log=None)
    await runner.setup()
    site=web.TCPSite(runner,os.getenv('PLATEGA_WEBHOOK_HOST','127.0.0.1'),
                    int(os.getenv('PLATEGA_WEBHOOK_PORT','8090')))
    await site.start()
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await client.close()
