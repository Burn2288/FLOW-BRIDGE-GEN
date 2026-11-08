"""DarkFlow provider-neutral discovery and protocol registry.
Public catalogue, key availability, documented operation and executable handler are
separate facts. Model names/tags never authorize routing or pricing.
"""
import asyncio,hashlib,json,re,time
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
import httpx
from .discovery import DiscoveryError,SchemaProfile,normalize,snapshot,SnapshotStore

BRAND='DarkFlow | Gen'

@dataclass(frozen=True)
class Operation:
    id: str
    title: str
    method: str
    path: str
    fields: tuple[str,...]=()
    preview_supported: bool=False

# Once per protocol, never one branch per brand/model. None of these descriptors
# themselves permits an unquoted, unreserved or unapproved financial call.
PROTOCOLS=(
 Operation('chat','Текстовый диалог','POST','/v1/chat/completions',('prompt',),True),
 Operation('responses','Ответы и рассуждения','POST','/v1/responses',('prompt',),True),
 Operation('messages','Диалог с вложениями','POST','/v1/messages'),
 Operation('images.generate','Создание изображений','POST','/v1/images/generations',('prompt',),True),
 Operation('images.edit','Редактирование изображений','POST','/v1/images/edits'),
 Operation('audio.speech','Озвучка текста','POST','/v1/audio/speech',('text','voice'),True),
 Operation('audio.voices','Каталог голосов','GET','/v1/audio/voices'),
 Operation('audio.cloning','Создание голоса','POST','/v1/audio/clones'),
 Operation('audio.change_voice','Изменение голоса','POST','/v1/audio/voice-changer'),
 Operation('audio.transcribe','Распознавание речи','POST','/v1/audio/transcriptions'),
 Operation('audio.translate','Перевод аудио','POST','/v1/audio/translations'),
 Operation('audio.generate','Аудио и музыка','POST','/v1/audios'),
 Operation('audio.estimate','Оценка аудиозадачи','POST','/v1/audios/estimate'),
 Operation('embeddings','Векторизация текста','POST','/v1/embeddings'),
 Operation('audio.dubbing.init','Загрузка для дубляжа','POST','/v1/audio/dubbing/upload/init'),
)
BY_ID={x.id:x for x in PROTOCOLS}
PATH_TO_OPERATION={x.path:x.id for x in PROTOCOLS}

class Adapter(Protocol):
    async def collect(self)->dict: ...

class ProviderRegistry:
    def __init__(self):
        self.adapters = {}
        self.prices = {}
        self.launches = {}
        self.interactive = {}

    def register(self,provider,adapter=None,*,price=None,launch=None,title=None):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}',provider) or provider in self.adapters:
            raise DiscoveryError('Invalid/duplicate provider')
        if title is not None and (len(provider)>15 or adapter is None or price is None or launch is None):
            raise DiscoveryError('Interactive provider requires catalogue, price and execution')
        self.adapters[provider] = adapter
        if price is not None:
            self.prices[provider] = price
        if launch is not None:
            self.launches[provider] = launch
        if title is not None:
            self.interactive[provider] = title

    async def collect(self,provider=None):
        models=[];functions=[];sources=[]
        adapters = self.adapters.items() if provider is None else [(provider,self.adapters[provider])]
        for key,adapter in adapters:
            if adapter is None:
                continue
            data=await adapter.collect()
            for model in data['models']:
                models.append(dict(model,provider=key,key=key+':'+model['id']))
            for fn in data['functions']:
                functions.append(dict(fn,provider=key))
            sources.append({'provider':key,'scope':data['scope'],'evidence':data.get('evidence',{})})
        return make_snapshot(models,functions,sources)

def safe_string(value,limit=256):
    if not isinstance(value,str) or not value or len(value)>limit or any(ord(c)<32 for c in value):raise DiscoveryError('Invalid catalogue field')
    return value

def public_metadata(pricing):
    if not isinstance(pricing,dict) or pricing.get('success') is not True or not isinstance(pricing.get('data'),list):raise DiscoveryError('Invalid public catalogue schema')
    if len(pricing['data'])>10000:raise DiscoveryError('Catalogue too large')
    records={}
    for r in pricing['data']:
        if not isinstance(r,dict):raise DiscoveryError('Invalid model metadata')
        ident=safe_string(r.get('model_name'))
        if ident in records:raise DiscoveryError('Duplicate public model')
        protocols=r.get('supported_endpoint_types',[])
        if not isinstance(protocols,list) or any(not isinstance(x,str) or len(x)>80 for x in protocols):raise DiscoveryError('Invalid protocol metadata')
        price={}
        for name in ('model_price','usage_fixed_price','cached_usage_fixed_price','final_price','model_ratio','completion_ratio'):
            if name in r and not isinstance(r[name],bool):
                try:d=Decimal(str(r[name]))
                except Exception:raise DiscoveryError('Invalid numeric metadata') from None
                if not d.is_finite() or d<0:raise DiscoveryError('Invalid numeric metadata')
                price[name]=str(d)
        unit=r.get('usage_fixed_price_unit')
        if unit is not None:price['unit']=safe_string(unit,100)
        price['verified_for_billing']=False
        records[ident]={'protocols':protocols,'public_pricing':price}
    return records

def documented_functions(docs,pricing):
    if not isinstance(docs,dict) or docs.get('schema_version')!=1 or not isinstance(docs.get('sections'),list):raise DiscoveryError('Unknown documentation schema')
    if len(docs['sections'])>200:raise DiscoveryError('Documentation limit')
    paths=set();methods={};routes=set()
    for section in docs['sections']:
        if not isinstance(section,dict):raise DiscoveryError('Invalid documentation section')
        # Routes are evidence strings only. Never execute code, examples or remote instructions.
        lists=[section.get(k,[]) for k in ('details','links','examples')]
        if any(not isinstance(v,list) for v in lists):raise DiscoveryError('Invalid documentation fields')
        fields=[line for values in lists for line in values]
        for line in fields:
            if not isinstance(line,str):continue
            for path in re.findall(r'/v1/[A-Za-z0-9_/:.{}-]+',line):paths.add(path.rstrip('.'))
            for method,path in re.findall(r'\b(GET|POST|DELETE|PUT|PATCH|WSS)\s+(?:https://clodex\.xyz)?(/v1/[A-Za-z0-9_/:.{}-]+)',line):
                path=path.rstrip('.');methods[path]=method;routes.add((method,path))
    endpoints=pricing.get('supported_endpoint',{})
    if not isinstance(endpoints,dict):raise DiscoveryError('Invalid endpoint index')
    for info in endpoints.values():
        if isinstance(info,dict) and info.get('method') in ('GET','POST','DELETE','PUT','PATCH'):
            path=info.get('path','')
            if isinstance(path,str) and re.fullmatch(r'/v1/[A-Za-z0-9_/-]+',path) and '..' not in path:
                paths.add(path);methods[path]=info['method'];routes.add((info['method'],path))
    # Expand documented grouped upload notation; no arbitrary caller-selected URLs.
    if '/v1/audio/dubbing/upload/{init' in paths:paths.add('/v1/audio/dubbing/upload/init')
    for method,path in list(routes):
        if path.endswith('/{init'):
            routes.remove((method,path))
            for suffix in ('init','chunk','complete'):routes.add((method,path[:-5]+suffix))
    out=[];handled=set()
    for spec in PROTOCOLS:
        if spec.path in paths:
            handled.add((spec.method,spec.path))
            out.append({'id':spec.id,'title':spec.title,'method':spec.method,'path':spec.path,
                        'fields':list(spec.fields),'request_preview_supported':spec.preview_supported,
                        'published':True,'live_verified':False,'paid_execution_enabled':False})
    # Unknown new routes are visible as unimplemented, not silently discarded or executed.
    for method,path in sorted(routes-handled):
        if len(path)>200:continue
        out.append({'id':'discovered-'+hashlib.sha256((method+' '+path).encode()).hexdigest()[:12],
                    'title':'Дополнительная операция','method':method,'path':path,
                    'fields':[],'request_preview_supported':False,'published':True,'live_verified':False,'paid_execution_enabled':False})
    # Index every published documentation section, including capabilities whose
    # exact API route/schema has NOT been published (e.g. video). Never invent one.
    for section in docs['sections']:
        ident=safe_string(section.get('id'),100);title=safe_string(section.get('title'),200)
        summary=section.get('summary','')
        if not isinstance(summary,str) or len(summary)>4000:raise DiscoveryError('Invalid documentation summary')
        out.append({'id':'documentation-'+ident,'title':'📖 '+title,'method':'UNCONFIRMED','path':'',
                    'summary':summary,'documentation_only':True,'fields':[],
                    'request_preview_supported':False,'published':True,'live_verified':False,'paid_execution_enabled':False})
    return sorted(out,key=lambda x:(x['title'],x['id']))

def make_snapshot(models,functions,sources):
    models=sorted(models,key=lambda m:(m['provider'],m['id']))
    data=snapshot(models)
    # Raw response hashes can change while the menu entries stay identical.
    menu_sources=[{k:v for k,v in source.items() if k!='evidence'} for source in sources]
    body={'models':models,'functions':functions,'sources':menu_sources}
    data.update(functions=functions,sources=sources)
    data['version']=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:12]
    return data

class ClodexAdapter:
    def __init__(self,key='',profile=None,client=None):
        self.key=key;self.profile=profile or SchemaProfile();self.source_hashes={}
        self.client=client or httpx.AsyncClient(timeout=httpx.Timeout(20,connect=5),follow_redirects=False)
    async def get_json(self,path,authenticated=False):
        if path not in ('/api/pricing','/docs-v2.json','/v1/models'):raise DiscoveryError('Unapproved discovery route')
        headers={'Authorization':'Bearer '+self.key} if authenticated and self.key else {}
        if authenticated and not self.key:raise DiscoveryError('Key missing')
        try:
            async with self.client.stream('GET','https://clodex.xyz'+path,headers=headers) as r:
                if r.status_code!=200:raise DiscoveryError('Discovery HTTP error')
                raw=bytearray()
                async for chunk in r.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw)>4*1024*1024:raise DiscoveryError('Discovery response limit')
                value=json.loads(raw,parse_float=Decimal)
                self.source_hashes[path]=hashlib.sha256(raw).hexdigest()
                return value
        except (httpx.HTTPError,ValueError):raise DiscoveryError('Discovery transport/schema error') from None
    async def collect(self):
        self.source_hashes.clear()
        models = None
        if self.key:
            models = normalize(await self.get_json('/v1/models', True), self.profile)
        unavailable = []
        try:
            pricing = await self.get_json('/api/pricing')
            meta = public_metadata(pricing)
        except DiscoveryError:
            if models is None:
                raise
            pricing, meta = {}, {}
            unavailable.append('/api/pricing')
        try:
            docs = await self.get_json('/docs-v2.json')
            functions = documented_functions(docs, pricing)
        except DiscoveryError:
            functions = []
            unavailable.append('/docs-v2.json or endpoint metadata')
        scope = 'key_available' if models is not None else 'public_only'
        if models is None:
            models = normalize({'data': [{'id': model_id} for model_id in meta]})
        for m in models:
            m.update(meta.get(m['id'],{'protocols':[],'public_pricing':{'verified_for_billing':False}}))
            m['availability']=scope
        return {'models':models,'functions':functions,'scope':scope,
                'evidence':{'unavailable_metadata':unavailable,'source_sha256':dict(self.source_hashes),'public_models':len(meta),'selected_models':len(models),
                            'capabilities_inferred_from_names':False,'public_prices_are_billing_proof':False}}
    async def refresh(self,store):
        registry=ProviderRegistry();registry.register('clodex',self)
        data=await registry.collect();await asyncio.to_thread(store.write,data);return data
    async def close(self):await self.client.aclose()

async def refresh_aggregate(cfg,once=False):
    adapter=ClodexAdapter(cfg.clodex_key,SchemaProfile.load(cfg.catalogue_profile))
    try:
        while True:
            try:
                data=await adapter.refresh(SnapshotStore(cfg.catalogue_path))
                if once:return data
                print(json.dumps({'event':'aggregate_refresh_ok','models':len(data['models']),
                                  'functions':len(data['functions']),'sources':data['sources']}),flush=True)
            except (DiscoveryError,OSError):
                if once:raise
                print(json.dumps({'event':'aggregate_refresh_failed'}),flush=True)
            await asyncio.sleep(300)
    finally:await adapter.close()

def prepare_request(data,provider,operation,model,fields):
    """Validate a generic protocol request without sending or billing it."""
    if data['fresh_until']<time.time():raise DiscoveryError('Stale catalogue')
    spec=BY_ID.get(operation)
    declared=next((f for f in data.get('functions',[]) if f['provider']==provider and f['id']==operation),None)
    if not spec or not declared or not spec.preview_supported:raise DiscoveryError('Protocol not implemented')
    if declared.get('path')!=spec.path or declared.get('method')!=spec.method:raise DiscoveryError('Protocol contract mismatch')
    record=next((m for m in data['models'] if m['provider']==provider and m['id']==model),None)
    if not record:raise DiscoveryError('Model absent')
    if not isinstance(fields,dict) or set(fields)!=set(spec.fields):raise DiscoveryError('Unknown/missing input fields')
    values={k:safe_string(v,4096) for k,v in fields.items()}
    if operation=='chat':body={'model':model,'messages':[{'role':'user','content':values['prompt']}]}
    elif operation=='responses':body={'model':model,'input':values['prompt']}
    elif operation=='images.generate':body={'model':model,'prompt':values['prompt']}
    else:body={'model':model,'input':values['text'],'voice':values['voice']}
    return {'provider':provider,'operation':operation,'method':spec.method,'path':spec.path,'body':body,
            'model_operation_verified':operation in record['operations'],
            'availability':record['availability'],'paid_execution_enabled':False}
