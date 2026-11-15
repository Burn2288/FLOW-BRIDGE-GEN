"""Read-only Mini App over the same account and work services as Telegram."""

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from importlib.resources import files
from urllib.parse import parse_qsl
from uuid import UUID

from aiohttp import web

from .core import Rejected, Service

INIT_MAX_AGE = 300
SESSION_SECONDS = 600


def verified_identity(raw, bot_token, *, now):
    if not isinstance(raw, str) or len(raw) > 8192 or not bot_token:
        raise ValueError('Invalid Telegram data')
    pairs = parse_qsl(raw, strict_parsing=True, errors='strict', max_num_fields=32)
    data = dict(pairs)
    if len(data) != len(pairs) or any(
        not key.isascii() or not key.replace('_', '').isalnum() or '\n' in value or '\r' in value
        for key, value in pairs
    ):
        raise ValueError('Invalid Telegram fields')
    supplied = data.pop('hash', '')
    message = '\n'.join(f'{key}={value}' for key, value in sorted(data.items()))
    key = hmac.digest(b'WebAppData', bot_token.encode(), 'sha256')
    expected = hmac.digest(key, message.encode(), 'sha256')
    if len(supplied) != 64 or not hmac.compare_digest(expected, bytes.fromhex(supplied)):
        raise ValueError('Invalid Telegram signature')
    age = now - int(data.get('auth_date', '0'))
    if not -30 <= age <= INIT_MAX_AGE:
        raise ValueError('Expired Telegram data')
    user = json.loads(data.get('user', 'null'))
    external = user.get('id') if isinstance(user, dict) else None
    if type(external) is not int or not 0 < external < 2**52:
        raise ValueError('Invalid Telegram user')
    return external, expected


def token_hash(token):
    return hashlib.sha256(token.encode()).digest()


@web.middleware
async def headers(request, handler):
    try:
        response = await handler(request)
    except web.HTTPException as error:
        response = web.Response(status=error.status, body=error.body, headers=error.headers)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = (
        "default-src 'none'; script-src 'self' https://telegram.org; connect-src 'self'; "
        "style-src 'self'; base-uri 'none'; form-action 'none'"
    )
    return response


def create_app(pool, cfg):
    service = Service(pool, cfg)
    from .telegram import TelegramApp, STORE_SECTIONS, anymodel_available
    view = TelegramApp(pool, cfg, None)
    app = web.Application(client_max_size=12 * 1024, middlewares=[headers])

    async def login(request):
        try:
            body = await request.json()
            external, signed = verified_identity(body.get('initData'), cfg.token, now=time.time())
        except (AttributeError, ValueError):
            raise web.HTTPUnauthorized(text='Откройте приложение заново из Telegram.') from None
        token = secrets.token_urlsafe(32)
        async with pool.acquire() as conn, conn.transaction():
            user = await conn.fetchval(
                "SELECT user_id FROM identities WHERE platform='telegram' AND external_id=$1", external
            )
            try:
                await service.authorize(conn, user)
            except Rejected:
                raise web.HTTPForbidden(text='Сначала откройте бот и примите условия.') from None
            await conn.execute('DELETE FROM miniapp_sessions WHERE expires_at<=now()')
            created = await conn.fetchval(
                """INSERT INTO miniapp_sessions(token_hash,init_hash,user_id,expires_at) VALUES($1,$2,$3,now()+$4*interval '1 second')
                   ON CONFLICT(init_hash) DO NOTHING RETURNING true""",
                token_hash(token), signed, user, SESSION_SECONDS
            )
            if not created:
                raise web.HTTPUnauthorized(text='Откройте приложение заново из Telegram.')
        return web.json_response({'token': token, 'expires_in': SESSION_SECONDS})

    async def account(request):
        scheme, _, token = request.headers.get('Authorization', '').partition(' ')
        if scheme != 'Bearer' or len(token) != 43:
            raise web.HTTPUnauthorized()
        async with pool.acquire() as conn:
            user = await conn.fetchval(
                'SELECT user_id FROM miniapp_sessions WHERE token_hash=$1 AND expires_at>now() AND NOT revoked',
                token_hash(token)
            )
            if user is None:
                raise web.HTTPUnauthorized()
            try:
                await service.authorize(conn, user)
            except Rejected:
                raise web.HTTPForbidden() from None
        return user

    async def wallet(request):
        user = await account(request)
        row = await service.wallet(user)
        return web.json_response({key: str(row[key]) for key in ('available', 'reserved')})

    async def catalogue(request):
        await account(request)
        # The HTTP account is read-only and has no Admin Edition session.
        rows = []
        availability = {}
        try:
            snap = view.catalogue_snapshot()
        except Rejected:
            snap = None
        label = view.provider_title(None, 'clodex')
        availability[label] = snap is not None
        if snap is not None:
            for section, (_, operation) in STORE_SECTIONS.items():
                for index in await view.store_models(snap, section, None):
                    item = snap['models'][index]
                    rows.append(dict(aggregator=label,id=item['id'],title=item['title'],operation=operation))

        if anymodel_available(cfg):
            label = view.provider_title(None, 'anymodel')
            try:
                snap = view.anymodel_snapshot(None)
            except Rejected:
                snap = None
            ready = view.anymodel_catalogue_ready(snap)
            availability[label] = ready
            if ready:
                approved = {(row['model_id'], row['operation']) for row in await view.models.list('anymodel')}
                for item in snap['models']:
                    if item['availability'] == 'key_available':
                        for operation in item['operations']:
                            if (item['id'], operation) in approved:
                                rows.append(dict(aggregator=label,id=item['id'],title=item['title'],operation=operation))
        # fal is restricted in the bot to its owner's active Admin Edition.
        # A regular HTTP session never inherits that privilege.
        return web.json_response({'models': rows, 'availability': availability})

    async def history(request):
        user = await account(request)
        try:
            page = int(request.query.get('page', '0'))
            if not 0 <= page <= 10000:
                raise ValueError()
        except ValueError:
            raise web.HTTPBadRequest() from None
        rows = await service.history(user, page * 10)
        return web.json_response({'works': [
            dict(id=str(row['id']), kind=row['kind'], model=row['model_id'],
                 status=row['status'], available=bool(row['file_available']),
                 created_at=row['created_at'].isoformat()) for row in rows
        ]})

    async def result(request):
        user = await account(request)
        kind = request.match_info['kind']
        try:
            work_id = UUID(request.match_info['id'])
            if kind == 'chat':
                data = (await service.chat_work(user, work_id)).encode()
                suffix = 'txt'
            else:
                method, suffix = {'image': (service.image_work, 'png'),
                                  'audio': (service.audio_work, 'mp3'),
                                  'video': (service.video_work, 'mp4')}[kind]
                row = await method(user, work_id)
                data = row[kind]
                if kind == 'image' and data.startswith(b'\xff\xd8'):
                    suffix = 'jpg'
        except (KeyError, ValueError, Rejected):
            raise web.HTTPNotFound() from None
        return web.Response(body=data, content_type='application/octet-stream',
                            headers={'Content-Disposition': f'attachment; filename="darkflow.{suffix}"'})

    async def logout(request):
        await account(request)
        await pool.execute('UPDATE miniapp_sessions SET revoked=true WHERE token_hash=$1',
                           token_hash(request.headers['Authorization'][7:]))
        return web.Response(status=204)

    async def asset(request):
        name = request.match_info.get('asset', 'index.html')
        mime = {'index.html': 'text/html', 'app.js': 'text/javascript', 'style.css': 'text/css'}
        if name not in mime:
            raise web.HTTPNotFound()
        return web.Response(body=files('elevenbot').joinpath('miniapp', name).read_bytes(),
                            content_type=mime[name], charset='utf-8')

    app.router.add_get('/', asset)
    app.router.add_get('/assets/{asset}', asset)
    app.router.add_post('/api/v1/session', login)
    app.router.add_delete('/api/v1/session', logout)
    app.router.add_get('/api/v1/catalogue', catalogue)
    app.router.add_get('/api/v1/wallet', wallet)
    app.router.add_get('/api/v1/works', history)
    app.router.add_get('/api/v1/works/{kind}/{id}', result)
    return app


async def serve(pool, cfg):
    if not cfg.token:
        raise ValueError('TELEGRAM_BOT_TOKEN required')
    runner = web.AppRunner(create_app(pool, cfg), access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, '0.0.0.0', int(os.getenv('MINIAPP_PORT', '8091'))).start()
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
