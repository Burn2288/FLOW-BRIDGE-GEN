"""Closed AnyModel speech pilot with a durable, one-use price confirmation."""

import asyncio
from contextlib import nullcontext
from decimal import Decimal
from hashlib import sha256
import json
import subprocess

import httpx

from .anymodel import AnyModelError, AnyModelProvider, BASE, can_view
from .core import Rejected
from .interaction import trace_interaction

FISH = 'fish-farm/s2.1-pro-free'
FISH_TITLE = 'Fish Audio S2.1 Pro Free'
SPEECH_PATH = '/audio/speech'
MAX_AUDIO = 20 * 1024 * 1024


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


def voice_key(model):
    return sha256(model.encode()).hexdigest()[:24]


class SpeechPilot:
    def __init__(self, pool, cfg, *, api=None):
        self.pool, self.cfg = pool, cfg
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
        return await self.api.anyvoice_voices()

    @staticmethod
    def voice_title(voice):
        return voice['name'][:80]+' · AnyVoice'+(' (ИИ-имитация)' if voice.get('imitation') is True else '')

    async def title(self, model):
        if model == FISH:
            rows = await self.catalogue('/models/tts')
            if not any(row.get('id') == FISH for row in rows):
                raise AnyModelError('модель недоступна', code='speech_model')
            return FISH_TITLE
        voice = (await self.voices()).get(model)
        if voice is None:
            raise AnyModelError('голос недоступен', code='speech_voice')
        return self.voice_title(voice)

    async def prepare(self, conn, user, quote):
        req = quote.request
        await conn.execute("""
            INSERT INTO task_speech_works(id,user_id,model_id,title,input,cost_tokens,claimed,expires_at)
            VALUES($1,$2,$3,$4,$5,$6,true,now()+interval '7 days')
            """, quote.id,user,req.model,req.title,req.prompt,Decimal(quote.price['base']))

    async def synthesize(self, quote, model, prompt, title, *, track=None):
        async with track(title) if track else nullcontext():
            try:
                reply = await self.api.read_response('POST',BASE+SPEECH_PATH,authenticated=True,
                    max_body=MAX_AUDIO,deadline=120,submission=True,timeout=httpx.Timeout(90,connect=5),
                    json={'model':model,'input':prompt})
                if reply.content_type not in ('audio/mpeg','audio/mp3'):
                    raise AnyModelError('неизвестный формат ответа', code='speech_content_type')
                await asyncio.to_thread(validate_mp3, reply.body)
            except AnyModelError as error:
                trace_interaction(str(quote),'anymodel_speech_failed',reason=error.code)
                detail = 'Исход запроса неизвестен.' if error.status is None and error.code in (
                    'response_timeout','transport_error','connect_timeout','connect_error',
                ) else 'Не удалось получить озвучку.'
                raise Rejected(f'{detail} Запрос автоматически не повторяется.') from None
            await self.pool.execute('UPDATE task_speech_works SET audio=$2 WHERE id=$1', quote, reply.body)
        return quote
