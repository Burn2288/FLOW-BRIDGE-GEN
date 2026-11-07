"""AnyModel catalogue and explicitly selected test chat."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time

import httpx

from .aggregate import ProviderRegistry
from .discovery import DiscoveryError, SnapshotStore, normalize
from .core import Rejected
from .interaction import decode_result, download_image, image_url, trace_interaction

BASE = 'https://anymodel.org/v1'
PUBLIC_PRICING = 'https://anymodel.org/en/pricing'
TEST_MODEL = 'ds/deepseek-v4-flash-vision'
FIBO_MODEL = 'anymedia/fibo-2'
IMAGE_OP = 'images.generate'
IMAGE_ENDPOINT = BASE+'/images/generations'
JOB_ID = re.compile(r'[A-Za-z0-9_-]{1,180}')
MAX_BODY = 4 * 1024 * 1024
MODEL_ID = re.compile(r'[A-Za-z0-9_.:@-]+(?:/[A-Za-z0-9_.:@-]+)+')


class AnyModelError(Exception):
    def __init__(self,message,*,code='protocol',status=None,retry_after=5):
        super().__init__(message)
        self.code,self.status,self.retry_after=code,status,retry_after


@dataclass(frozen=True)
class ProviderReply:
    status: int
    retry_after: float
    body: bytes
    content_type: str
    connection_id: str | None


def retry_after(value):
    if value:
        try:
            if value.isascii() and value.isdigit():
                return min(float(value), 31_536_000)
            when=parsedate_to_datetime(value)
            if when.tzinfo is None:
                when=when.replace(tzinfo=timezone.utc)
            return max(0,(when-datetime.now(timezone.utc)).total_seconds())
        except (ValueError,TypeError,OverflowError):
            pass
    return 5


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


def can_image(model, data):
    return (model['provider'] == 'anymodel' and model['id'] == FIBO_MODEL
            and model['availability'] == 'key_available' and IMAGE_OP in model['operations']
            and data['fresh_until'] > time.time())


class AnyModelProvider:
    def __init__(self, key, *, client=None):
        self.key = key
        self.client = client

    async def request(self,method,url,*,authenticated,**kwargs):
        return (await self.read_response(method,url,authenticated=authenticated,**kwargs)).body

    async def read_response(self,method,url,*,authenticated,max_body=MAX_BODY,accepted=(200,),
                            request_headers=None,**kwargs):
        if authenticated and not self.key:
            raise AnyModelError('тестовый ключ отсутствует')
        headers=dict(request_headers or {})
        if authenticated:headers['Authorization']='Bearer '+self.key
        async def read(client):
            async with asyncio.timeout(25), client.stream(
                method, url, headers=headers, follow_redirects=False, **kwargs
            ) as response:
                delay=retry_after(response.headers.get('Retry-After'))
                if response.status_code not in accepted:
                    raise AnyModelError(f'HTTP {response.status_code}',code=f'http_{response.status_code}',
                                        status=response.status_code,retry_after=delay)
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(raw) + len(chunk) > max_body:
                        raise AnyModelError('превышен размер ответа',code='response_size',status=response.status_code)
                    raw.extend(chunk)
                return ProviderReply(response.status_code,delay,bytes(raw),
                                     response.headers.get('content-type','').split(';')[0].lower(),
                                     response.headers.get('x-9router-connection-id'))
        try:
            if self.client is not None:
                return await read(self.client)
            async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), trust_env=False) as client:
                return await read(client)
        except (httpx.ConnectError,httpx.ConnectTimeout) as error:
            code='connect_timeout' if isinstance(error,httpx.ConnectTimeout) else 'connect_error'
            raise AnyModelError('сетевая ошибка',code=code) from None
        except (httpx.ReadTimeout,TimeoutError):
            raise AnyModelError('сетевая ошибка',code='response_timeout') from None
        except httpx.HTTPError:
            raise AnyModelError('сетевая ошибка',code='transport_error') from None

    @staticmethod
    def decode(raw):
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise AnyModelError('некорректный JSON',code='invalid_json') from None

    async def collect(self):
        payload = self.decode(await self.request('GET', BASE+'/models', authenticated=True))
        return self.catalogue(payload, 'key_available')

    @staticmethod
    def catalogue(payload, scope):
        try:
            models = normalize(payload)
        except DiscoveryError:
            raise AnyModelError('неизвестный формат каталога') from None
        image_ids = {record['id'] for record in payload['data'] if record.get('kind') == 'image'}
        for model in models:
            if model['id'] in image_ids:
                model.update(operations=[IMAGE_OP],capabilities_known=True,protocols=['openai-images'])
            if model['id'] == FIBO_MODEL:
                if model['title'] == FIBO_MODEL:
                    model['title'] = 'FIBO 2'
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

    async def submit_image(self,model,prompt):
        if model != FIBO_MODEL:
            raise AnyModelError('модель генерации изображения недоступна')
        return await self.read_response('POST',IMAGE_ENDPOINT,authenticated=True,max_body=8*1024*1024,
                                        accepted=(200,202),json={'model':model,'prompt':prompt,'background':True})

    async def poll_image(self,job_id):
        if not JOB_ID.fullmatch(job_id):
            raise AnyModelError('некорректный ID задачи',code='job_id')
        return await self.read_response('GET',f'{IMAGE_ENDPOINT}/{job_id}',authenticated=True,
                                        max_body=8*1024*1024,accepted=(200,202))

    def accepted_image_id(self,reply):
        data=self.decode(reply.body)
        job_id=data.get('id') if isinstance(data,dict) else None
        if not isinstance(job_id,str) or not JOB_ID.fullmatch(job_id):
            raise AnyModelError('некорректный ID задачи',code='job_id')
        return job_id

    async def image_result(self,reply,request_id):
        payload=self.decode(reply.body)
        try:
            result=await asyncio.to_thread(decode_result,IMAGE_OP,payload)
        except Rejected:
            url=image_url(payload)
            if not url:
                trace_interaction(request_id,'anymodel_image_result',format='other')
                raise AnyModelError('ответ не содержит поддерживаемого изображения',code='image_invalid') from None
        else:
            trace_interaction(request_id,'anymodel_image_result',format='b64_json')
            return result
        trace_interaction(request_id,'anymodel_image_result',format='url')
        try:
            if self.client is not None:
                return await download_image(self.client,url,request_id)
            async with httpx.AsyncClient(trust_env=False,limits=httpx.Limits(max_keepalive_connections=0)) as media:
                return await download_image(media,url,request_id)
        except (Rejected,TimeoutError):
            raise AnyModelError('не удалось скачать или проверить изображение',code='image_download') from None

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
