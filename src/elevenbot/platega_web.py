"""Private callback listener. TLS/public routing is an explicit deployment task."""
import asyncio,os
from aiohttp import web
from .platega import PlategaClient,PlategaConfig,PlategaPayments,PaymentInvalid,PaymentUnknown

def create_app(payments):
    app=web.Application(client_max_size=65536)
    async def callback(request):
        if not payments.client.authenticated(request.headers):return web.Response(status=401)
        try:await payments.callback(request.headers,await request.read())
        except PermissionError:return web.Response(status=401)
        except PaymentInvalid:return web.Response(status=400)
        except PaymentUnknown:return web.Response(status=503)
        except web.HTTPRequestEntityTooLarge:raise
        except Exception:return web.Response(status=503)
        return web.Response(status=200)
    app.router.add_post('/payments/platega/callback',callback)
    return app

async def serve(pool,cfg):
    pc=PlategaConfig(merchant=os.getenv('PLATEGA_MERCHANT_ID',''),secret=os.getenv('PLATEGA_SECRET',''),
        enabled=os.getenv('PLATEGA_ENABLED','false').lower()=='true',return_url=os.getenv('PLATEGA_RETURN_URL',''),
        failed_url=os.getenv('PLATEGA_FAILED_URL',''))
    if not pc.enabled or not pc.merchant or not pc.secret:raise ValueError('Platega not configured')
    client=PlategaClient(pc);payments=PlategaPayments(pool,cfg,client)
    runner=web.AppRunner(create_app(payments),access_log=None);await runner.setup()
    # No public port by default. Reverse proxy/TLS must be explicitly configured later.
    site=web.TCPSite(runner,'127.0.0.1',8090);await site.start()
    try:await asyncio.Event().wait()
    finally:await runner.cleanup();await client.close()
