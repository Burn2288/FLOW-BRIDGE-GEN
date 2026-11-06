"""Read-only model discovery. No brand lists and no inferred capabilities from model IDs.
SchemaProfile is an operator-reviewed mapping of API metadata, not a claim about
undocumented Clodex response fields. Default accepts IDs, leaves capabilities unknown.
"""
import asyncio,hashlib,json,os,time,uuid,math
from dataclasses import dataclass,field
from pathlib import Path
import httpx

class DiscoveryError(Exception):pass

OPERATIONS={
 'chat':('Диалог','/v1/chat/completions'),
 'responses':('Ассистент','/v1/responses'),
 'images.generate':('Изображения','/v1/images/generations'),
 'images.edit':('Редактирование изображений',None),
 'messages':('Диалог с вложениями','/v1/messages'),
 'audio.speech':('Озвучка','/v1/audio/speech'),
 'audio.transcribe':('Распознавание речи','/v1/audio/transcriptions'),
 'audio.translate':('Перевод аудио','/v1/audio/translations'),
 'audio.change_voice':('Изменение голоса','/v1/audio/voice-changer'),
 'audio.generate':('Аудио и музыка','/v1/audios'),
 'audio.dubbing':('Дубляж',None),
 'audio.cloning':('Создание голоса','/v1/audio/clones'),
 'rerank':('Ранжирование документов',None),
 'embeddings':('Векторизация','/v1/embeddings'),
 'video':('Видео',None),
 'realtime':('Голосовой диалог',None),
}
# Registry is a bounded set of protocol contracts, NOT dynamically executed instructions.
# A known operation alone never authorizes a paid request or establishes pricing.

@dataclass(frozen=True)
class SchemaProfile:
    operations_path: tuple[str,...]=()
    operation_tokens: dict[str,str]=field(default_factory=dict)
    source_evidence: str=''

    @classmethod
    def load(cls,path=''):
        if not path:return cls()
        p=json.loads(Path(path).read_text(encoding="utf-8"))
        if set(p)-{'operations_path','operation_tokens','source_evidence'}:raise DiscoveryError('Unknown profile field')
        parts=p.get('operations_path',[]);mapping=p.get('operation_tokens',{});evidence=p.get('source_evidence','')
        if not isinstance(parts,list) or len(parts)>5 or any(not isinstance(x,str) or not x or len(x)>80 for x in parts):raise DiscoveryError('Invalid metadata path')
        if not isinstance(mapping,dict) or len(mapping)>100 or any(not isinstance(k,str) or v not in OPERATIONS for k,v in mapping.items()):raise DiscoveryError('Unknown operation mapping')
        if parts and not evidence:raise DiscoveryError('Reviewed schema evidence required')
        return cls(tuple(parts),mapping,evidence)

def text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 for c in value):raise DiscoveryError('Invalid model field')
    return value

def normalize(payload,profile=None):
    profile=profile or SchemaProfile()
    if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):raise DiscoveryError('Unrecognized model-list schema')
    if len(payload['data'])>10000:raise DiscoveryError('Catalogue limit')
    models=[];seen=set()
    for record in payload['data']:
        if not isinstance(record,dict):raise DiscoveryError('Invalid model record')
        ident=text(record.get('id'),256)
        if ident in seen:raise DiscoveryError('Duplicate model ID')
        seen.add(ident)
        # Only safe normalized fields are persisted; never copy provider instructions/URLs.
        title=record.get('name',ident)
        if not isinstance(title,str):title=ident
        title=''.join(c for c in title if ord(c)>=32)[:80] or ident[:80]
        node=record
        for part in profile.operations_path:
            node=node.get(part) if isinstance(node,dict) else None
        ops=[]
        if profile.operations_path and isinstance(node,list) and all(isinstance(x,str) for x in node):
            ops=sorted({profile.operation_tokens[x] for x in node if x in profile.operation_tokens})
        models.append({'id':ident,'title':title,'operations':ops,'capabilities_known':bool(ops)})
    return sorted(models,key=lambda x:x['id'])

def snapshot(models,ttl=900,now=None):
    now=time.time() if now is None else now
    if not 30<=ttl<=86400:raise DiscoveryError('Invalid TTL')
    canonical=json.dumps(models,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    return {'schema':1,'version':hashlib.sha256(canonical).hexdigest()[:12],
            'fetched_at':now,'fresh_until':now+ttl,'models':models}

class SnapshotStore:
    def __init__(self,path):self.path=Path(path)
    def write(self,data):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        tmp=self.path.with_name(self.path.name+'.'+uuid.uuid4().hex+'.tmp')
        fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:tmp.unlink(missing_ok=True)
    def read(self):
        try:data=json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError,ValueError,OSError):return None
        if not isinstance(data,dict) or data.get('schema')!=1 or not isinstance(data.get('models'),list):return None
        if not isinstance(data.get('fresh_until'),(int,float)) or not math.isfinite(data['fresh_until']) or not isinstance(data.get('version'),str):return None
        if any(not isinstance(m,dict) or not isinstance(m.get('id'),str) or not isinstance(m.get('title'),str) or not isinstance(m.get('operations'),list) or any(op not in OPERATIONS for op in m['operations']) for m in data['models']):return None
        return data

class ClodexDiscovery:
    def __init__(self,key,profile=None,client=None):
        self.key=key;self.profile=profile or SchemaProfile()
        self.client=client or httpx.AsyncClient(timeout=httpx.Timeout(15,connect=5),follow_redirects=False)
    async def fetch(self):
        if not self.key:raise DiscoveryError('API key required for read-only discovery')
        try:
            async with self.client.stream('GET','https://clodex.xyz/v1/models',headers={'Authorization':'Bearer '+self.key}) as r:
                if r.status_code!=200:raise DiscoveryError('Catalogue unavailable')
                raw=bytearray()
                async for chunk in r.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw)>4*1024*1024:raise DiscoveryError('Response limit')
                return normalize(json.loads(raw),self.profile)
        except (httpx.HTTPError,ValueError):raise DiscoveryError('Catalogue transport/schema error') from None
    async def refresh(self,store):
        models=await self.fetch()
        data=snapshot(models);await asyncio.to_thread(store.write,data)
        return data
    async def close(self):await self.client.aclose()

async def refresh_loop(cfg):
    from .aggregate import refresh_aggregate
    await refresh_aggregate(cfg)

def groups(data):
    found={op for m in data['models'] for op in m['operations'] if op in OPERATIONS}
    result=[{'id':op,'title':OPERATIONS[op][0],'models':[m for m in data['models'] if op in m['operations']]} for op in sorted(found)]
    unknown=[m for m in data['models'] if not m['operations']]
    if unknown:result.append({'id':'unclassified','title':'Новые модели','models':unknown})
    return result

def execution_status(model,fresh,registered_handlers=(),priced_models=()):
    if not fresh:return 'stale_catalogue'
    if not model['operations']:return 'capabilities_unknown'
    if not set(model['operations'])&set(registered_handlers):return 'protocol_not_implemented'
    if model['id'] not in priced_models:return 'price_unverified'
    return 'eligible_for_contract_validation'  # NOT permission to bypass quote/balance/limits.
