"""fal Model Platform, pricing and the Lyria queue contract."""

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from decimal import Decimal, InvalidOperation

import httpx

from .anymodel_speech import validate_mp3
from .clodex_music import MAX_MP3, OPERATION, MusicPilot
from .core import Rejected
from .pricing import NoProviderPrice, PriceUnavailable, ProviderCost
from .submission import ProviderRefused
from .video import ID_PATTERN, VideoProtocolError

PLATFORM = 'https://api.fal.ai'
QUEUE = 'https://queue.fal.run'
LYRIA = 'google/lyria-3.5'
CATEGORIES = {
    'text-to-audio': OPERATION, 'text-to-speech': 'audio.speech',
    'text-to-image': 'images.generate', 'image-to-image': 'images.edit',
    'text-to-video': 'video', 'image-to-video': 'video', 'video-to-video': 'video',
    'speech-to-text': 'audio.transcribe', 'text-to-text': 'chat',
}


class FalProvider:
    def __init__(self, key, *, transport=None):
        self.key, self.transport = key, transport
        self.lock = asyncio.Lock()
        self.catalogue = None
        self.fresh_until = 0

    def client(self, *, authenticated=True):
        headers = {'Authorization': 'Key '+self.key} if authenticated and self.key else {}
        return httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(20, connect=5),
                                 trust_env=False, follow_redirects=False, transport=self.transport)

    async def json(self, method, url, **kwargs):
        async with asyncio.timeout(25), self.client() as client:
            async with client.stream(method, url, **kwargs) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes(65536):
                    body.extend(chunk)
                    if len(body) > 4 * 1024 * 1024:
                        raise VideoProtocolError('fal_json_size')
        payload = json.loads(body, parse_float=Decimal)
        if not isinstance(payload, dict):
            raise VideoProtocolError('fal_json_shape')
        return payload

    async def collect(self):
        async with self.lock:
            if self.catalogue is not None and self.fresh_until > time.monotonic():
                return self.catalogue
            try:
                self.catalogue = await self.collect_pages()
            except (httpx.HTTPError, TimeoutError, ValueError, VideoProtocolError, TypeError):
                if self.catalogue is None:
                    raise Rejected('Каталог fal временно недоступен.') from None
                self.fresh_until = time.monotonic() + 30
                self.catalogue = {**self.catalogue, 'evidence': {'stale': True}}
                return self.catalogue
            self.fresh_until = time.monotonic() + 300
            return self.catalogue

    async def collect_pages(self):
        cursor = None
        cursors = set()
        models = {}
        async with asyncio.timeout(120):
            for _ in range(300):
                params = {'limit': 100}
                if cursor:
                    params['cursor'] = cursor
                body = await self.catalogue_page(params)
                if not isinstance(body.get('models'), list) or type(body.get('has_more')) is not bool:
                    raise VideoProtocolError('fal_catalogue_shape')
                for entry in body['models']:
                    model = self.model(entry)
                    models[model['id']] = model
                cursor = body.get('next_cursor')
                if not body['has_more'] and cursor is None:
                    return {'models': list(models.values()), 'functions': [], 'scope': 'public_only'}
                if not isinstance(cursor, str) or not cursor or len(cursor)>4096 or cursor in cursors:
                    raise VideoProtocolError('fal_catalogue_cursor')
                cursors.add(cursor)
                await asyncio.sleep(0.15)
        raise VideoProtocolError('fal_catalogue_page_limit')

    async def catalogue_page(self, params):
        for attempt in range(3):
            try:
                return await self.json('GET', PLATFORM+'/v1/models', params=params)
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 429 or attempt==2:
                    raise
                raw = error.response.headers.get('retry-after', '')
                try:
                    delay = int(raw) if raw.isdigit() else (parsedate_to_datetime(raw)
                                                           - datetime.now(timezone.utc)).total_seconds()
                except (TypeError,ValueError,OverflowError):
                    delay = 2**attempt
                await asyncio.sleep(max(1,delay))

    def model(self, entry):
        ident = entry.get('endpoint_id') if isinstance(entry, dict) else None
        if not isinstance(ident,str) or not re.fullmatch(r'[\w.-]+(?:/[\w.-]+)+',ident,re.ASCII) or len(ident)>256:
            raise VideoProtocolError('fal_endpoint_id')
        meta = entry.get('metadata') or {}
        if not isinstance(meta, dict):
            raise VideoProtocolError('fal_model_metadata')
        category = meta.get('category')
        category = category if isinstance(category, str) and re.fullmatch(r'[a-z0-9-]{1,80}',category) else None
        title = meta.get('display_name') or ident
        if not isinstance(title,str):
            title = ident
        operation = CATEGORIES.get(category)
        launchable = self.supports(ident,operation) and meta.get('status')=='active'
        return {'id': ident, 'title': title[:100], 'protocols': [category] if category else [],
                'operations': [operation] if operation else [],
                'availability': 'public_only', 'registered_launchable': launchable}

    def supports(self, model, operation):
        return bool(self.key and model==LYRIA and operation==OPERATION)

    @staticmethod
    def usd(value):
        if type(value) not in (int, Decimal, str):
            raise PriceUnavailable()
        try:
            amount = Decimal(value)
        except InvalidOperation:
            raise PriceUnavailable() from None
        if not amount.is_finite() or amount < 0 or amount > 1000:
            raise PriceUnavailable()
        return amount

    async def unit_price(self, endpoint):
        try:
            body = await self.json('GET',PLATFORM+'/v1/models/pricing',params={'endpoint_id':endpoint})
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise NoProviderPrice() from None
            raise
        prices = body.get('prices')
        if not isinstance(prices,list):
            raise PriceUnavailable()
        matches = [p for p in prices if isinstance(p,dict) and p.get('endpoint_id')==endpoint]
        if not matches:
            raise NoProviderPrice()
        if len(matches)!=1 or matches[0].get('currency')!='USD':
            raise PriceUnavailable()
        return self.usd(matches[0].get('unit_price')),matches[0].get('unit')

    async def cost(self, request):
        if request.provider!='fal' or not self.supports(request.model,request.operation):
            raise PriceUnavailable()
        if request.params or not request.prompt.strip() or len(request.prompt)>4000 or '\x00' in request.prompt:
            raise PriceUnavailable()
        try:
            rate, unit = await self.unit_price(request.model)
            if unit not in ('generation','generations','request','requests'):
                raise NoProviderPrice()
            data = {'estimate_type':'unit_price','endpoints':{request.model:{'unit_quantity':1}}}
            try:
                result = await self.json('POST',PLATFORM+'/v1/models/pricing/estimate',json=data)
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in (404,405,422):
                    raise
                return ProviderCost(rate,'USD',True,'fal /v1/models/pricing','1 генерация')
            if result.get('estimate_type')!='unit_price' or result.get('currency')!='USD':
                raise PriceUnavailable()
            return ProviderCost(self.usd(result.get('total_cost')),'USD',True,
                                'fal /v1/models/pricing/estimate','1 генерация')
        except (httpx.HTTPError,TimeoutError,ValueError,VideoProtocolError):
            raise PriceUnavailable() from None

    @staticmethod
    def allows_manual(row):
        from .pricing import BOT_TOKEN
        return row['source_unit']==BOT_TOKEN and not row['temporary']

    async def create(self, prompt):
        try:
            body = await self.json('POST',f'{QUEUE}/{LYRIA}',json={'prompt':prompt})
        except httpx.HTTPStatusError as error:
            if error.response.status_code in (400,401,403,404,422,429):
                raise ProviderRefused('fal отклонил запрос.') from None
            raise
        task = body.get('request_id')
        if not isinstance(task,str) or not ID_PATTERN.fullmatch(task):
            raise VideoProtocolError('fal_request_id')
        return task

    async def status(self, task):
        body = await self.json('GET',f'{QUEUE}/{LYRIA}/requests/{task}/status')
        state = body.get('status')
        if state == 'COMPLETED':
            return 'failed' if body.get('error') else 'ready'
        if state in ('IN_QUEUE','IN_PROGRESS'):
            return 'polling'
        raise VideoProtocolError('fal_queue_status')

    async def download(self, task):
        try:
            body = await self.json('GET',f'{QUEUE}/{LYRIA}/requests/{task}')
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 422:
                raise ProviderRefused('fal сообщил об ошибке генерации.') from None
            raise
        media = body.get('audio')
        link = media.get('url') if isinstance(media,dict) else media
        if not isinstance(link,str):
            raise VideoProtocolError('fal_audio_url')
        try:
            url = httpx.URL(link)
        except httpx.InvalidURL:
            raise VideoProtocolError('fal_audio_url') from None
        if (url.scheme!='https' or url.port not in (None,443) or url.userinfo or not url.host
                or not (url.host=='fal.media' or url.host.endswith('.fal.media'))):
            raise VideoProtocolError('fal_audio_host')
        audio = bytearray()
        async with asyncio.timeout(60), self.client(authenticated=False) as client:
            async with client.stream('GET',url) as response:
                response.raise_for_status()
                if response.headers.get('content-type','').split(';',1)[0].lower() not in (
                        'audio/mpeg','audio/mp3','application/octet-stream'):
                    raise VideoProtocolError('fal_audio_type')
                async for chunk in response.aiter_bytes(65536):
                    audio.extend(chunk)
                    if len(audio)>MAX_MP3:
                        raise VideoProtocolError('fal_audio_size')
        result = bytes(audio)
        await asyncio.to_thread(validate_mp3,result)
        return result


class FalMusicPilot(MusicPilot):
    provider = 'fal'
    model = LYRIA
    title = 'Lyria 3.5'
    provider_title = 'fal'
    filename = 'lyria-3.5.mp3'
    params = {}

    def __init__(self,pool,cfg,*,api=None):
        super().__init__(pool,cfg,api=api or FalProvider(cfg.fal_key))

    def owner(self,chat):
        return (self.cfg.access_mode=='private' and not self.cfg.payments_enabled
                and bool(self.cfg.fal_key) and chat>0 and chat==self.cfg.fal_music_owner
                and chat in self.cfg.admin_ids)

    def enabled(self):
        return self.cfg.fal_music_live

    async def validate_model(self,conn,request):
        from .model_policy import admitted
        if not await admitted(conn,self.provider,self.model,OPERATION):
            raise Rejected('Модель не допущена к этой операции.')

