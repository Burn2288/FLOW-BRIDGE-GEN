"""Read-only Mini App over the same account and work services as Telegram."""

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qsl
from uuid import UUID

from aiohttp import web

from elevenbot.model_capabilities import FLUX_MODEL, flux_card, veo_card
from elevenbot.providers import catalog
from elevenbot.core import Rejected, Service
from elevenbot.library import LibraryItem
from elevenbot.job_timeline import get_timeline
from elevenbot.admission import admitted

INIT_MAX_AGE = 300
SESSION_SECONDS = 600
WEB_ROOT = Path(__file__).resolve().parents[1] / "frontend"


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
        "style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'"
    )
    return response


def create_app(pool, cfg, *, view=None, job_scheduler=None):
    service = Service(pool, cfg)
    from elevenbot.telegram import TelegramApp, STORE_SECTIONS, anymodel_available
    view = view if view is not None else TelegramApp(pool, cfg, None)
    app = web.Application(client_max_size=12 * 1024, middlewares=[headers])

    async def health(request):
        try:
            healthy = await pool.fetchval('SELECT 1') == 1
        except Exception:
            healthy = False
        return web.json_response({'status': 'ok' if healthy else 'unavailable'}, status=200 if healthy else 503)

    async def login(request):
        try:
            body = await request.json()
            external, signed = verified_identity(body.get('initData'), cfg.token, now=time.time())
        except (AttributeError, ValueError):
            raise web.HTTPUnauthorized(text='Откройте приложение заново из Telegram.') from None
        if not admitted(cfg,external):
            raise web.HTTPForbidden(text='Доступ к закрытому пилоту ограничен.')
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
            external = await conn.fetchval("SELECT external_id FROM identities WHERE platform='telegram' AND user_id=$1",user)
            if not admitted(cfg,external):
                raise web.HTTPForbidden()
            try:
                await service.authorize(conn, user)
            except Rejected:
                raise web.HTTPForbidden() from None
        return user

    async def wallet(request):
        user = await account(request)
        row = await service.wallet(user)
        return web.json_response({key: str(row[key]) for key in ('available', 'reserved')})

    async def music_access(user):
        if not cfg.clodex_music_owner:
            return False
        chat = await pool.fetchval("SELECT external_id FROM identities WHERE platform='telegram' AND user_id=$1", user)
        return await view.music.miniapp_access(pool, chat)

    async def catalogue(request):
        user = await account(request)
        rows = []
        availability = {}
        try:
            snap = view.catalogue_snapshot()
        except Rejected:
            snap = None
        label = view.provider_title(None, 'clodex')
        availability[label] = snap is not None
        if snap is not None:
            veo_titles = {}
            pilot = False
            if view.video.enabled() or cfg.speech_pilot:
                external = await pool.fetchval("SELECT external_id FROM identities WHERE platform='telegram' AND user_id=$1", user)
                try:
                    await view.launch.authorize_pilot(pool, user, external)
                except Rejected:
                    pass
                else:
                    pilot = True
            if pilot and view.video.enabled():
                veo_titles = {model: 'Veo 3.1 · '+label for model,label,_ in
                                  (await view.admitted_veo_modes(snap)).values()}
            for section, (_, operation) in STORE_SECTIONS.items():
                for index in await view.store_models(snap, section, None):
                    item = snap['models'][index]
                    row = dict(aggregator=label,id=item['id'],title=item['title'],operation=operation)
                    if item['id'] == FLUX_MODEL and operation == 'images.generate' and view.public_clodex_image(FLUX_MODEL, operation):
                        card = await flux_card(pool)
                        if card:
                            row['image_card'] = card
                    if operation == 'video' and item['id'] in veo_titles:
                        card = await veo_card(pool, item['id'])
                        if card:
                            row.update(title=veo_titles[item['id']], video_card=card)
                    if pilot and cfg.speech_pilot and operation == 'audio.speech' and view.model_can_run(item, operation):
                        voices = [voice['task_speech_capability'] for voice in catalog(cfg)]
                        row['speech_card'] = {'model': cfg.clodex_model, 'voices': voices}
                    rows.append(row)

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
        if view.music.enabled() and await music_access(user):
            rows.append(dict(aggregator='CLODEX', id=view.music.model, title=view.music.title, operation='audio.generate',
                             music_card={'used': await view.music.used(user)}))
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
        rows = await service.history(user, page * 10, include_pending_tasks=True,
                                     include_music=await music_access(user))
        return web.json_response({'works': [LibraryItem.from_history(row).as_dict() for row in rows]})

    async def timeline(request):
        user = await account(request)
        try:
            data = await get_timeline(pool, service, user, request.match_info['kind'], request.match_info['id'])
        except Rejected:
            raise web.HTTPNotFound() from None
        return web.json_response(data)

    async def result(request):
        user = await account(request)
        kind = request.match_info['kind']
        try:
            work_id = UUID(request.match_info['id'])
            if kind == 'music':
                if not await music_access(user):
                    raise web.HTTPNotFound()
                data = await view.music.work(user, work_id)
                suffix = 'mp3'
            elif kind == 'chat':
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

    async def settings(request):
        user = await account(request)
        if request.method == 'PUT':
            try:
                body = await request.json()
            except ValueError:
                raise web.HTTPBadRequest() from None
            if not isinstance(body, dict) or set(body) != {'theme'} or body['theme'] not in ('dark', 'light'):
                raise web.HTTPBadRequest()
            theme = await pool.fetchval(
                'UPDATE users SET miniapp_theme=$2 WHERE id=$1 AND NOT blocked RETURNING miniapp_theme',
                user, body['theme'])
        else:
            theme = await pool.fetchval(
                'SELECT miniapp_theme FROM users WHERE id=$1 AND NOT blocked', user)
        if theme is None:
            raise web.HTTPForbidden()
        return web.json_response({'theme': theme})

    async def asset(request):
        name = request.match_info.get('asset', 'index.html')
        mime = {'index.html': ('index.html', 'text/html'), 'app.js': ('app.js', 'text/javascript'),
                'style.css': ('style.css', 'text/css'),
                'darkflow-banner.png': ('assets/darkflow-banner.png', 'image/png')}
        if name not in mime:
            raise web.HTTPNotFound()
        path, content_type = mime[name]
        return web.Response(body=await asyncio.to_thread((WEB_ROOT / path).read_bytes),
                            content_type=content_type)

    app.router.add_get('/', asset)
    app.router.add_get('/healthz', health)
    app.router.add_get('/assets/{asset}', asset)
    app.router.add_post('/api/v1/session', login)
    app.router.add_delete('/api/v1/session', logout)
    app.router.add_get('/api/v1/catalogue', catalogue)
    app.router.add_get('/api/v1/wallet', wallet)
    app.router.add_get('/api/v1/settings', settings)
    app.router.add_put('/api/v1/settings', settings)
    app.router.add_get('/api/v1/works', history)
    app.router.add_get('/api/v1/works/{kind}/{id}/timeline', timeline)
    app.router.add_get('/api/v1/works/{kind}/{id}', result)
    from .image_commands import add_routes
    add_routes(app, pool=pool, cfg=cfg, view=view, account=account, scheduler=job_scheduler)
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
