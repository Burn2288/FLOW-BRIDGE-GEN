"""Disposable studio profile using the production adapters without external I/O."""

import base64
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import re
import time
from uuid import uuid4

import httpx

from elevenbot.aggregate import make_snapshot
from elevenbot.clodex_music import AUDIOS
from elevenbot.config import Config
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE

ROOT = Path(__file__).resolve().parents[1]
VOICE = 'fixture-voice'
SPEECH_MODEL = 'eleven_v4'
VIDEO_MODEL = 'clodex-video/veo-3.1'
SEED_ADMIN = 199
KEY = 'fixture-only'


def dev_config():
    cfg = Config.env()
    return replace(
        cfg, access_mode='private', mode='clodex', cost_per_char=1, budget=None,
        admin_ids=(100, 102, 103, SEED_ADMIN), pilot_user_ids=(101, 104),
        admin_password='fixture-password', bot_username='FlowBridgeFixtureBot',
        catalogue_path=str(cfg.storage.parent / 'catalogue' / 'models.json'),
        clodex_key=KEY, economy_verified=True, clodex_model=SPEECH_MODEL,
        clodex_music_owner=100, fixture_music_owners=(102,), clodex_music_live=True,
        public_image_models=('clodex:flux-schnell',), interaction_mode='live',
        interaction_limit=100, video_pilot=True, speech_pilot=True,
    )


def provider_response(request):
    method, path = request.method, request.url.path
    if request.url.host != 'clodex.xyz' or request.headers.get('Authorization') != 'Bearer ' + KEY:
        return httpx.Response(403)
    if (method, path) == ('GET', '/v1/audio/voices'):
        return httpx.Response(200, json={'voices': [{'voice_id': VOICE, 'name': 'Тестовый голос'}]})
    if (method, path) == ('POST', '/v1/audio/speech'):
        return httpx.Response(200, content=(ROOT / 'assets/demo.mp3').read_bytes(),
                              headers={'Content-Type': 'audio/mpeg'})
    if (method, path) == ('POST', '/v1/images/generations'):
        return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(MOCK_IMAGE).decode()}]})
    if method == 'POST' and path in ('/v1/videos/estimate', AUDIOS + '/estimate'):
        model = json.loads(request.content)['model']
        return httpx.Response(200, json={'success': True, 'data': {'model': model, 'cost_usd': '0.1'}})
    if method == 'POST' and path in ('/v1/videos', AUDIOS):
        return httpx.Response(200, json={'id': 'fixture-' + uuid4().hex})
    match = re.fullmatch(r'/v1/(videos|audios)/fixture-[0-9a-f]{32}(/content)?', path)
    if method == 'GET' and match:
        kind, content = match.groups()
        if not content:
            return httpx.Response(200, json={'status': 'done'})
        media, mimetype = {
            'videos': ('src/elevenbot/darkflow-energy-strip-1200x80-2x.mp4', 'video/mp4'),
            'audios': ('assets/demo.mp3', 'audio/mpeg'),
        }[kind]
        return httpx.Response(200, content=(ROOT / media).read_bytes(), headers={'Content-Type': mimetype})
    return httpx.Response(404)


@contextmanager
def offline_clients():
    # Provider HTTP in this launcher has no network fallback.
    from unittest.mock import patch
    client_class = httpx.AsyncClient

    def client(*args, **kwargs):
        return client_class(*args, **(kwargs | {'transport': httpx.MockTransport(provider_response)}))

    with patch.object(httpx, 'AsyncClient', client):
        yield


async def seed(pool, cfg):
    from elevenbot.consent import CURRENT_VERSION
    from elevenbot.telegram import TelegramApp

    rows = [('flux-schnell', 'FLUX Schnell', 'images.generate', ['image-generation']),
            (VIDEO_MODEL, 'Veo 3.1', 'video', ['openai-video']),
            ('eleven-v4', 'ElevenLabs v4', 'audio.speech', [])]
    models = [dict(provider='clodex', id=model, title=title, availability='key_available',
                   operations=[operation], protocols=protocols)
              for model, title, operation, protocols in rows]
    snapshot = make_snapshot(models, [], [dict(provider='clodex', scope='key_available')])
    snapshot['fresh_until'] = time.time() + 7 * 86400
    SnapshotStore(cfg.catalogue_path).write(snapshot)
    cfg.voice_catalogue_path.write_text(
        json.dumps([{'id': VOICE, 'name': 'Тестовый голос'}], ensure_ascii=False), encoding='utf-8')

    app = TelegramApp(pool, cfg, None)
    try:
        admin = await app.svc.identity(SEED_ADMIN)
        await app.svc.accept(admin, CURRENT_VERSION)
        for external in (100, 101, 102):
            user = await app.svc.identity(external)
            async with pool.acquire() as conn, conn.transaction():
                await app.svc.movement(conn, user, 'live', f'dev-studio-{external}', 'pilot_grant', 10000, 0)
        for model, operation, params, basis in (
            ('flux-schnell', 'images.generate', {'n': 1}, 'request'),
            (SPEECH_MODEL, 'audio.speech', {'voice': VOICE}, 'utf16'),
        ):
            await app.pricing.set_tariff(
                admin, SEED_ADMIN, 'clodex', model, operation, params, basis=basis,
                unit='darkflow_token', amount='2', expires=None, evidence='offline-dev-fixture',
            )
        await app.pricing.set_rate(admin, SEED_ADMIN, 'USD', '1000')
    finally:
        await app.topups.client.close()
