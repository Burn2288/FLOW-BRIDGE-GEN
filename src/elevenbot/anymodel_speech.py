"""Closed AnyModel speech pilot with a durable, one-use price confirmation."""

import asyncio
from decimal import Decimal, InvalidOperation
import json
import subprocess
from uuid import uuid4

import httpx

from .anymodel import AnyModelError, AnyModelProvider, BASE, MODEL_ID, can_view
from .core import Rejected, Service, uid
from .interaction import trace_interaction

FISH = 'fish-farm/s2.1-pro-free'
FISH_TITLE = 'Fish Audio S2.1 Pro Free'
SPEECH_PATH = '/audio/speech'
MAX_AUDIO = 20 * 1024 * 1024
MAX_TEXT = 4000


def token_rate(billing):
    if not isinstance(billing, dict) or billing.get('unit') != 'character':
        return None
    base, coefficient = billing.get('base_tokens'), billing.get('coefficient')
    output = coefficient.get('output') if isinstance(coefficient, dict) else None
    if type(base) is not int or not 0 <= base <= 1_000_000 or type(output) not in (int, float, str):
        return None
    try:
        output = Decimal(str(output))
        if not output.is_finite() or not 0 <= output <= 1_000_000:
            return None
        # Reject unsupported precision instead of rounding a quoted cost.
        if output.as_tuple().exponent < -12:
            return None
        return base * output
    except InvalidOperation:
        return None


def validate_mp3(audio):
    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-f', 'mp3', '-count_frames', '-show_entries',
             'stream=codec_name,nb_read_frames', '-of', 'json', '-i', 'pipe:0'],
            input=audio, capture_output=True, check=True, timeout=10,
        )
        stream, = json.loads(probe.stdout)['streams']
        if stream['codec_name'] == 'mp3' and int(stream['nb_read_frames']) > 0:
            return
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
        pass
    raise AnyModelError('некорректный MP3', code='speech_mp3')


class SpeechPilot:
    def __init__(self, pool, cfg, *, api=None):
        self.pool, self.cfg = pool, cfg
        self.svc = Service(pool, cfg)
        self.api = api or AnyModelProvider(cfg.anymodel_key)

    def enabled(self, external):
        return (can_view(self.cfg, external) and self.cfg.anymodel_speech_live
                and not self.cfg.payments_enabled and self.cfg.interaction_limit > 0
                and bool(self.cfg.anymodel_key))

    async def get(self, path, params=None):
        return self.api.decode(await self.api.request('GET', BASE+path, authenticated=True, params=params))

    async def catalogue(self, path, params=None):
        payload = await self.get(path, params)
        rows = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise AnyModelError('неизвестный формат каталога', code='speech_catalogue')
        return [row for row in rows if isinstance(row, dict)]

    async def voices(self):
        rows = await self.catalogue('/audio/voices', {'provider':'anyvoice', 'lang':'ru'})
        return {row['model']: row for row in rows
                if isinstance(row.get('model'), str) and row['model'].startswith('anyvoice/')
                and MODEL_ID.fullmatch(row['model']) and len('amvoice:'+row['model']) <= 64
                and row.get('lang') == 'ru' and isinstance(row.get('name'), str) and row['name'].strip()}

    async def model(self, model):
        if model == FISH:
            rows = await self.catalogue('/models/tts')
            if not any(row.get('id') == FISH for row in rows):
                raise AnyModelError('модель недоступна', code='speech_model')
            title, rate = FISH_TITLE, None
        else:
            voice = (await self.voices()).get(model)
            if voice is None:
                raise AnyModelError('голос недоступен', code='speech_voice')
            title = voice['name'][:80]+' · AnyVoice'
            if voice.get('imitation') is True:
                title += ' (ИИ-имитация)'
            rate = token_rate(voice.get('billing'))
        if rate is None:
            try:
                info = await self.get('/models/info', {'id':model})
            except AnyModelError as error:
                if error.status != 404:
                    raise
            else:
                if (isinstance(info, dict) and info.get('id') == model
                        and info.get('endpoint') == '/v1'+SPEECH_PATH):
                    rate = token_rate(info.get('billing'))
        return title, rate

    async def quote(self, user, model, input_text):
        if not input_text.strip() or '\x00' in input_text:
            raise Rejected('AnyModel: отправьте текст для озвучки.')
        units = len(input_text.encode('utf-16-le')) // 2
        if units > MAX_TEXT:
            raise Rejected(f'AnyModel: максимум {MAX_TEXT} единиц UTF-16.')
        title, rate = await self.model(model)
        if rate is None:
            raise Rejected('AnyModel: тариф не подтверждён. Тестовый запуск закрыт.')
        quote, cost = uuid4(), rate * units
        async with self.pool.acquire() as conn:
            await self.svc.authorize(conn, user)
            await conn.execute("""
                INSERT INTO anymodel_speech(id,user_id,model_id,title,input,cost_tokens)
                VALUES($1,$2,$3,$4,$5,$6)
                """, quote, user, model, title, input_text, cost)
        return quote, title, units, cost

    async def confirm(self, user, external, quote, update_id):
        if not self.enabled(external):
            raise Rejected('AnyModel: тестовый запуск озвучки выключен.')
        quote = uid(quote)
        async with self.pool.acquire() as conn:
            await self.svc.authorize(conn, user)
            row = await conn.fetchrow("""
                SELECT model_id,input,cost_tokens FROM anymodel_speech
                WHERE id=$1 AND user_id=$2 AND NOT claimed AND expires_at>now()
                """, quote, user)
        if not row:
            raise Rejected('AnyModel: оценка устарела или запрос уже принят.')
        _, rate = await self.model(row['model_id'])
        units = len(row['input'].encode('utf-16-le')) // 2
        if rate is None or rate * units != row['cost_tokens']:
            raise Rejected('AnyModel: цена изменилась или не подтверждена. Запросите новую оценку.')
        async with self.pool.acquire() as conn, conn.transaction():
            await self.svc.authorize(conn, user)
            claimed = await conn.fetchval("""
                UPDATE anymodel_speech SET claimed=true,expires_at=now()+interval '7 days'
                WHERE id=$1 AND user_id=$2 AND NOT claimed AND expires_at>now() RETURNING id
                """, quote, user)
            if not claimed or not await self.svc.reserve_interaction_on(conn,user,update_id,unlimited=False):
                raise Rejected('AnyModel: оценка устарела или запрос уже принят.')
        try:
            reply = await self.api.read_response('POST',BASE+SPEECH_PATH,authenticated=True,
                max_body=MAX_AUDIO,deadline=120,timeout=httpx.Timeout(90,connect=5),
                json={'model':row['model_id'],'input':row['input']})
            if reply.content_type not in ('audio/mpeg','audio/mp3'):
                raise AnyModelError('неизвестный формат ответа', code='speech_content_type')
            await asyncio.to_thread(validate_mp3, reply.body)
        except AnyModelError as error:
            trace_interaction(str(quote),'anymodel_speech_failed',reason=error.code)
            raise Rejected('AnyModel: результат озвучки не подтверждён. Запрос автоматически не повторяется.') from None
        await self.pool.execute('UPDATE anymodel_speech SET audio=$2 WHERE id=$1', quote, reply.body)
        return quote
