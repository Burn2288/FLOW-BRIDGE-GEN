"""Owned HTTP image commands over existing pricing, dispatch and wallet services."""
import asyncio
import re
from contextlib import nullcontext
from uuid import UUID

from aiohttp import web

from elevenbot.core import Rejected
from elevenbot.model_policy import admitted
from elevenbot.pricing import Request
from elevenbot.task_wallet import settle_task_tokens

KEY = re.compile(r'^[A-Za-z0-9_-]{8,96}$')
MODEL = 'flux-schnell'


def parse_uuid(value):
    try:
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise web.HTTPBadRequest() from None


def add_routes(app, *, pool, cfg, view, account, scheduler=None):
    running = set()

    async def body(request):
        try:
            value = await request.json()
        except (ValueError, TypeError):
            raise web.HTTPBadRequest() from None
        if not isinstance(value, dict):
            raise web.HTTPBadRequest()
        return value

    async def external_for(user):
        return await pool.fetchval("SELECT external_id FROM identities WHERE user_id=$1 AND platform='telegram'", user)

    async def create_quote(request):
        user = await account(request)
        data = await body(request)
        if set(data) != {'model', 'prompt'} or data['model'] != MODEL or not isinstance(data['prompt'], str):
            raise web.HTTPBadRequest()
        prompt = data['prompt'].strip()
        if not 1 <= len(prompt) <= 3000 or any(ord(c) < 32 and c not in '\n\r\t' for c in prompt):
            raise web.HTTPBadRequest()
        external = await external_for(user)
        if not cfg.allows_public_image('clodex', MODEL, 'images.generate'):
            raise web.HTTPForbidden()
        req = Request('clodex', MODEL, 'images.generate', 'FLUX Schnell', prompt, {'n': 1})
        try:
            async with pool.acquire() as conn:
                if not await admitted(conn, req.provider, req.model, req.operation):
                    raise Rejected('Model unavailable')
            if not view.clodex_launch_model(external, req):
                raise Rejected('Model unavailable')
            quote = await view.pricing.quote(user, req)
        except Rejected:
            raise web.HTTPForbidden(text='Оценка недоступна.') from None
        return web.json_response({'quote_id': str(quote.id), 'price': quote.price}, status=201)

    async def run_safely(run):
        try:
            await run()
        except Exception:
            # TaskLaunch persists rejected/uncertain; never retry a provider POST.
            pass

    def enqueue(run):
        if scheduler is not None:
            scheduler(run)
            return
        task = asyncio.create_task(run_safely(run))
        running.add(task)
        task.add_done_callback(running.discard)

    async def create_job(request):
        user = await account(request)
        key = request.headers.get('Idempotency-Key', '')
        data = await body(request)
        if not KEY.fullmatch(key) or set(data) != {'quote_id'}:
            raise web.HTTPBadRequest()
        quote_id = parse_uuid(data['quote_id'])
        external = await external_for(user)
        deferred = []
        try:
            async with pool.acquire() as conn, conn.transaction():
                await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1, 0))', str(user) + ':' + key)
                old = await conn.fetchrow('SELECT quote_id FROM http_image_commands WHERE user_id=$1 AND idempotency_key=$2', user, key)
                if old:
                    if old['quote_id'] != quote_id:
                        raise web.HTTPConflict(text='Ключ уже использован для другой команды.')
                    return web.json_response({'id': str(quote_id)}, status=200)
                owned = await conn.fetchval("""SELECT 1 FROM task_price_quotes WHERE id=$1 AND user_id=$2
                    AND provider='clodex' AND model_id=$3 AND operation='images.generate'""", quote_id, user, MODEL)
                if not owned:
                    raise web.HTTPNotFound()
                correlation = await conn.fetchval("SELECT -nextval('http_image_correlation_seq')")
                quote, accepted, _ = await view.launch.confirm(user, external, quote_id, correlation,
                    progress=lambda _: nullcontext(), background=None,
                    defer=lambda q, run: deferred.append(run))
                if not accepted:
                    raise web.HTTPConflict(text='Стоимость изменилась. Запросите новую оценку.')
                await conn.execute('INSERT INTO http_image_commands(user_id,idempotency_key,quote_id,correlation_id) VALUES($1,$2,$3,$4)',
                                   user, key, quote_id, correlation)
        except Rejected:
            raise web.HTTPConflict(text='Задание недоступно для подтверждения.') from None
        enqueue(deferred[0])
        return web.json_response({'id': str(quote.id)}, status=201)

    async def get_jobs(user, job_id=None):
        rows = await pool.fetch("""SELECT q.id,q.model_id,d.state,w.id AS work_id,h.cancelled_at,
                   (h.quote_id IS NOT NULL) AS http_origin
            FROM task_price_quotes q JOIN task_dispatch d ON d.quote_id=q.id
            LEFT JOIN http_image_commands h ON h.quote_id=q.id AND h.user_id=q.user_id
            LEFT JOIN image_works w ON w.update_id=q.update_id AND w.user_id=q.user_id AND w.expires_at>now()
            WHERE q.user_id=$1 AND q.operation='images.generate' AND ($2::uuid IS NULL OR q.id=$2)
            ORDER BY q.accepted_at DESC LIMIT 100""", user, job_id)
        return [{'id': str(r['id']), 'model': r['model_id'], 'state': 'cancelled' if r['cancelled_at'] else r['state'],
                 'origin': 'http' if r['http_origin'] else 'telegram',
                 'result_url': '/api/v1/works/image/' + str(r['work_id']) if r['work_id'] else None}
                for r in rows]

    async def list_jobs(request):
        return web.json_response({'jobs': await get_jobs(await account(request))})

    async def get_job(request):
        user = await account(request)
        rows = await get_jobs(user, parse_uuid(request.match_info['id']))
        if not rows:
            raise web.HTTPNotFound()
        return web.json_response(rows[0])

    async def cancel(request):
        user = await account(request)
        job_id = parse_uuid(request.match_info['id'])
        async with pool.acquire() as conn, conn.transaction():
            state = await conn.fetchval("""UPDATE task_dispatch d SET state='interrupted'
                FROM task_price_quotes q WHERE d.quote_id=q.id AND q.id=$1 AND q.user_id=$2
                AND q.operation='images.generate' AND d.state='pending'
                AND EXISTS (SELECT 1 FROM http_image_commands h WHERE h.quote_id=q.id AND h.user_id=q.user_id)
                RETURNING d.state""", job_id, user)
            if state:
                await conn.execute('UPDATE http_image_commands SET cancelled_at=now() WHERE quote_id=$1 AND user_id=$2', job_id, user)
                await settle_task_tokens(conn, job_id)
                return web.json_response({'cancelled': True, 'state': 'cancelled'})
            row = await conn.fetchrow("""SELECT d.state,h.cancelled_at FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id
                LEFT JOIN http_image_commands h ON h.quote_id=q.id AND h.user_id=q.user_id
                WHERE q.id=$1 AND q.user_id=$2 AND q.operation='images.generate'""", job_id, user)
            if row is None:
                raise web.HTTPNotFound()
            was_cancelled = row['cancelled_at'] is not None
            return web.json_response({'cancelled': was_cancelled, 'state': 'cancelled' if was_cancelled else row['state']})

    app.router.add_post('/api/v1/quotes', create_quote)
    app.router.add_post('/api/v1/jobs', create_job)
    app.router.add_get('/api/v1/jobs', list_jobs)
    app.router.add_get('/api/v1/jobs/{id}', get_job)
    app.router.add_post('/api/v1/jobs/{id}/cancel', cancel)
