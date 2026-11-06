from typing import Protocol
from pathlib import Path
import json
import os
import tempfile
import time
import httpx

from .interaction import provider_request_id, trace_interaction

class UnknownOutcome(Exception): pass
class DefinitiveFailure(Exception): pass

class Provider(Protocol):
    async def synthesize(self,text: str,voice: str,speed: float) -> bytes: ...

def catalog(cfg):
    if cfg.mode=='mock':return [{'id':'demo','name':'Демо-звук (не озвучка ElevenLabs)','preview':'assets/demo.mp3'}]
    path=cfg.voice_catalogue_path
    if path is None:return []
    try:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        if cfg.speech_pilot:return []
        raise
    if not isinstance(data,list) or any(not isinstance(v.get('id'),str) or not isinstance(v.get('name'),str) for v in data): raise ValueError('Invalid voice catalog')
    return data

class DisabledProvider:
    async def synthesize(self,*args,**kwargs):raise DefinitiveFailure('GENERATION_DISABLED')

class MockProvider:
    """Pre-generated tone, explicitly NOT ElevenLabs speech."""
    def __init__(self,path=None): self.path=Path(path) if path else Path(__file__).resolve().parents[2]/'assets'/'demo.mp3';self.calls=0
    async def synthesize(self,text,voice,speed):
        self.calls+=1
        return self.path.read_bytes()

class ClodexProvider:
    """Synchronous endpoint published at /docs-v2.md; no automatic paid retry."""
    def __init__(self,cfg,client=None):
        self.cfg=cfg
        self.metadata={}
        self.client=client or httpx.AsyncClient(timeout=httpx.Timeout(120,connect=10),follow_redirects=False)
    async def synthesize(self,text,voice,speed):
        # Speed not in verified published minimal schema: do not silently pass invented field.
        if speed!=1.0:raise DefinitiveFailure('UNSUPPORTED_SETTING')
        request_id=provider_request_id.get()
        endpoint='https://clodex.xyz/v1/audio/speech'
        started=time.monotonic()
        trace_interaction(request_id,'http_start',method='POST',endpoint=endpoint,request_fields=['input','model','voice'])
        try:
            async with self.client.stream('POST',endpoint,headers={
                'Authorization':'Bearer '+self.cfg.clodex_key,'Content-Type':'application/json'},
                json={'model':self.cfg.clodex_model,'voice':voice,'input':text}) as r:
                # All HTTP errors conservatively unknown until actual billing semantics verified.
                content_type=r.headers.get('content-type','').split(';')[0]
                audio=content_type in ('audio/mpeg','audio/mp3')
                trace_interaction(request_id,'http_headers',status=r.status_code,
                                  content_type=content_type if audio else 'other',
                                  elapsed_ms=round((time.monotonic()-started)*1000))
                if r.status_code!=200 or not audio:
                    trace_interaction(request_id,'provider_response_rejected')
                    raise UnknownOutcome('PROVIDER_RESPONSE')
                self.metadata={'request_id':(r.headers.get('x-clodex-request-id') or '')[:512],
                               'usage_characters':None}
                raw_usage=r.headers.get('x-clodex-usage-characters')
                if raw_usage and raw_usage.isdigit() and len(raw_usage)<12:
                    self.metadata['usage_characters']=int(raw_usage)
                out=bytearray()
                async for chunk in r.aiter_bytes():
                    out.extend(chunk)
                    if len(out)>20*1024*1024:raise UnknownOutcome('RESULT_TOO_LARGE')
                trace_interaction(request_id,'http_body_received',bytes=len(out),
                                  elapsed_ms=round((time.monotonic()-started)*1000))
                return bytes(out)
        except httpx.HTTPError as error:
            trace_interaction(request_id,'network_error',error_type=type(error).__name__)
            raise UnknownOutcome('PROVIDER_TRANSPORT') from None
    async def close(self): await self.client.aclose()


async def voice_candidates(key):
    """Read-only probe. Return voice IDs and display names without requesting speech."""
    if not key:
        raise ValueError('CLODEX_API_KEY required')
    async with httpx.AsyncClient(timeout=10,follow_redirects=False,trust_env=False) as client:
        async with client.stream(
            'GET','https://clodex.xyz/v1/audio/voices',
            params={'provider':'elevenlabs'},headers={'Authorization':'Bearer '+key},
        ) as response:
            if response.status_code!=200:
                return {'status':response.status_code,'candidates':[]}
            raw=bytearray()
            async for part in response.aiter_bytes(32768):
                if len(raw)+len(part)>1024*1024:
                    return {'status':200,'schema':'response_too_large','candidates':[]}
                raw.extend(part)
    payload=json.loads(raw)
    if isinstance(payload,dict):
        payload=payload.get('voices',payload.get('data'))
    if isinstance(payload,dict):
        payload=payload.get('voices')
    if not isinstance(payload,list):
        return {'status':200,'schema':'unrecognized','candidates':[]}
    candidates=[]
    for row in payload[:500]:
        if not isinstance(row,dict):
            continue
        ident=row.get('voice_id',row.get('id'))
        name=row.get('name')
        if isinstance(ident,str) and 0<len(ident)<=128 and all(c.isalnum() or c in '-_' for c in ident) and isinstance(name,str) and name.strip():
            candidates.append({'id':ident,'name':''.join(c for c in name if c.isprintable())[:80]})
    return {'status':200,'schema':'recognized','compatibility_verified':False,'candidates':candidates}


async def refresh_pilot_voices(cfg):
    result=await voice_candidates(cfg.clodex_key)
    voices=list({voice['id']:voice for voice in result['candidates']}.values())
    if not voices:
        return False
    path=cfg.voice_catalogue_path
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as stream:
        temporary=Path(stream.name)
    try:
        temporary.write_text(json.dumps(voices,ensure_ascii=False),encoding='utf-8')
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
    return True
