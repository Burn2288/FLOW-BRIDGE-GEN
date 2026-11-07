"""AnyModel catalogue and explicitly selected test chat."""

import asyncio
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time

import httpx

from .aggregate import ProviderRegistry
from .discovery import DiscoveryError, SnapshotStore, normalize

BASE = 'https://anymodel.org/v1'
PUBLIC_PRICING = 'https://anymodel.org/en/pricing'
TEST_MODEL = 'ds/deepseek-v4-flash-vision'
MAX_BODY = 4 * 1024 * 1024
MODEL_ID = re.compile(r'[A-Za-z0-9_.:@-]+(?:/[A-Za-z0-9_.:@-]+)+')


class AnyModelError(Exception):
    pass


class PricingModels(HTMLParser):
    """The pricing calculator exposes exact public IDs as option values."""

    def __init__(self):
        super().__init__()
        self.models = {}
        self.model = None
        self.title = []

    def handle_starttag(self, tag, attrs):
        if tag == 'option':
            ident = dict(attrs).get('value') or ''
            self.model = ident if MODEL_ID.fullmatch(ident) else None
            self.title = []

    def handle_data(self, data):
        if self.model:
            self.title.append(data)

    def handle_endtag(self, tag):
        if tag == 'option' and self.model:
            name = ''.join(self.title).partition(' · ')[0].strip()
            self.models[self.model] = {'id': self.model, 'name': name or self.model}
            self.model = None


def model_store(cfg):
    return SnapshotStore(Path(cfg.catalogue_path).with_name('anymodel.json'))


def can_view(cfg, external_id):
    return cfg.anymodel_test_enabled and cfg.access_mode == 'private' and external_id in cfg.admin_ids


def can_chat(model, data):
    return (model['provider'] == 'anymodel' and model['id'] == TEST_MODEL
            and model['availability'] == 'key_available' and 'chat' in model['operations']
            and data['fresh_until'] > time.time())


class AnyModelProvider:
    def __init__(self, key, *, client=None):
        self.key = key
        self.client = client

    async def request(self, method, url, *, authenticated, **kwargs):
        if authenticated and not self.key:
            raise AnyModelError('тестовый ключ отсутствует')
        headers = {'Authorization': 'Bearer '+self.key} if authenticated else {}
        async def read(client):
            async with asyncio.timeout(25), client.stream(
                method, url, headers=headers, follow_redirects=False, **kwargs
            ) as response:
                if response.status_code != 200:
                    raise AnyModelError(f'HTTP {response.status_code}')
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(raw) + len(chunk) > MAX_BODY:
                        raise AnyModelError('превышен размер ответа')
                    raw.extend(chunk)
                return raw
        try:
            if self.client is not None:
                return await read(self.client)
            async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), trust_env=False) as client:
                return await read(client)
        except (httpx.HTTPError, TimeoutError):
            raise AnyModelError('сетевая ошибка') from None

    @staticmethod
    def decode(raw):
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise AnyModelError('некорректный JSON') from None

    async def collect(self):
        payload = self.decode(await self.request('GET', BASE+'/models', authenticated=True))
        return self.catalogue(payload, 'key_available')

    @staticmethod
    def catalogue(payload, scope):
        try:
            models = normalize(payload)
        except DiscoveryError:
            raise AnyModelError('неизвестный формат каталога') from None
        for model in models:
            # Exact route documented for this ID. Do not infer other models' capabilities from their names.
            if model['id'] == TEST_MODEL:
                model.update(operations=['chat'], capabilities_known=True, protocols=['openai-chat'])
            model['availability'] = scope
        return {'models': models, 'functions': [], 'scope': scope}

    async def public_catalogue(self):
        raw = await self.request('GET', PUBLIC_PRICING, authenticated=False)
        parser = PricingModels()
        parser.feed(raw.decode('utf-8', errors='replace'))
        if not parser.models:
            raise AnyModelError('неизвестный формат публичного каталога')
        return self.catalogue({'data': list(parser.models.values())}, 'public_only')

    async def refresh(self, store):
        registry = ProviderRegistry()
        registry.register('anymodel', self)
        try:
            data = await registry.collect()
        except AnyModelError as error:
            data = await asyncio.to_thread(store.read)
            if data and data['sources'][0]['scope'] == 'key_available':
                data['fresh_until'] = 0
            else:
                try:
                    public = await self.public_catalogue()
                    from .aggregate import make_snapshot
                    models = [dict(m,provider='anymodel',key='anymodel:'+m['id']) for m in public['models']]
                    data = make_snapshot(models, [], [{'provider':'anymodel','scope':'public_only'}])
                except AnyModelError:
                    if not data:
                        raise error
                    data['fresh_until'] = 0
            data['refresh_error'] = str(error)
        await asyncio.to_thread(store.write,data)
        return data

    async def chat(self, model, prompt, history):
        if model != TEST_MODEL:
            raise AnyModelError('модель тестового чата недоступна')
        payload = {'model': model, 'messages': [*history, {'role':'user','content':prompt}],
                   'max_tokens': 256, 'stream': False}
        body = self.decode(await self.request('POST', BASE+'/chat/completions', authenticated=True, json=payload))
        try:
            reply = body['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise AnyModelError('некорректный ответ тестового чата') from None
        if not isinstance(reply, str) or not reply.strip():
            raise AnyModelError('пустой ответ тестового чата')
        return reply


async def refresh_anymodel(cfg, *, once=False):
    provider = AnyModelProvider(cfg.anymodel_key)
    while True:
        try:
            data = await provider.refresh(model_store(cfg))
            if once:
                return data
        except (AnyModelError,OSError):
            if once:
                raise
            print('anymodel_catalogue_refresh_failed',flush=True)
        await asyncio.sleep(300)
