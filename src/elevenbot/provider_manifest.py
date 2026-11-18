"""Strict metadata-only provider manifest validation; never creates or runs adapters."""
import re

from .discovery import DiscoveryError

# Exact routes present in existing adapters; inclusion does not establish live verification.
FAMILY_ENDPOINTS = {
    'clodex': frozenset({'https://clodex.xyz/v1/chat/completions',
                          'https://clodex.xyz/v1/images/generations',
                          'https://clodex.xyz/v1/audio/speech', 'https://clodex.xyz/v1/videos'}),
    'anymodel': frozenset({'https://anymodel.org/v1/chat/completions',
                            'https://anymodel.org/v1/images/generations',
                            'https://anymodel.org/v1/audio/speech',
                            'https://anymodel.org/v1/videos/generations'}),
    'fal': frozenset({'https://api.fal.ai/v1/models',
                       'https://api.fal.ai/v1/models/pricing',
                       'https://api.fal.ai/v1/models/pricing/estimate',
                       'https://queue.fal.run/google/lyria-3.5'}),
}
CREDENTIAL_REFS = {'clodex': 'CLODEX_API_KEY', 'anymodel': 'ANYMODEL_API_KEY', 'fal': 'FAL_KEY'}
FAMILY_OPERATIONS = {
    'clodex': frozenset({'chat', 'images.generate', 'audio.speech', 'video'}),
    'anymodel': frozenset({'chat', 'images.generate', 'audio.speech', 'video'}),
    'fal': frozenset({'audio.generate'}),
}
OPERATION_ROUTES = {
    'clodex': {'chat': ('text', 'https://clodex.xyz/v1/chat/completions'), 'images.generate': ('image', 'https://clodex.xyz/v1/images/generations'), 'audio.speech': ('audio', 'https://clodex.xyz/v1/audio/speech'), 'video': ('video', 'https://clodex.xyz/v1/videos')},
    'anymodel': {'chat': ('text', 'https://anymodel.org/v1/chat/completions'), 'images.generate': ('image', 'https://anymodel.org/v1/images/generations'), 'audio.speech': ('audio', 'https://anymodel.org/v1/audio/speech'), 'video': ('video', 'https://anymodel.org/v1/videos/generations')},
    'fal': {'audio.generate': ('music', 'https://queue.fal.run/google/lyria-3.5')},
}
NAME = re.compile(r'[a-z][a-z0-9_.-]{0,63}\Z', re.ASCII)
MODEL = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.:/@-]{0,255}\Z', re.ASCII)
PARAM = re.compile(r'[a-z][a-z0-9_]{0,63}\Z', re.ASCII)


class ManifestError(DiscoveryError):
    """Invalid manifest; messages are fixed, never echo manifest values."""


class UnsupportedAdapter(DiscoveryError):
    """No trusted adapter is installed for a manifest."""


def validate_manifest(value, *, registered, executable):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'provider', 'adapter_family', 'credential_ref', 'models'}:
        raise ManifestError('Invalid manifest structure')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ManifestError('Unsupported manifest version')
    provider, family, credential = value['provider'], value['adapter_family'], value['credential_ref']
    if not isinstance(provider,str) or not NAME.fullmatch(provider) or provider not in registered:
        raise ManifestError('Provider must already be registered')
    if not isinstance(family,str) or not NAME.fullmatch(family):
        raise ManifestError('Invalid adapter family')
    known = family in FAMILY_ENDPOINTS
    if known and provider != family:
        raise ManifestError('Provider and adapter family mismatch')
    if known and credential != CREDENTIAL_REFS[family]:
        raise ManifestError('Invalid credential reference')
    if not known and credential is not None:
        raise ManifestError('Unknown family cannot declare credentials')
    models = value['models']
    if not isinstance(models,list) or not 1 <= len(models) <= 1000:
        raise ManifestError('Invalid model list')
    cleaned=[]; ids=set(); unsupported=False
    for model in models:
        if not isinstance(model,dict) or set(model) != {'id','type','mode','endpoints','operations'}:
            raise ManifestError('Invalid model structure')
        ident=model['id']
        if not isinstance(ident,str) or not MODEL.fullmatch(ident) or '..' in ident or '://' in ident or ident in ids:
            raise ManifestError('Invalid model identifier')
        ids.add(ident)
        if model['type'] not in ('text','image','video','audio','music') or model['mode'] not in ('sync','async'):
            raise ManifestError('Invalid model type or mode')
        endpoints=model['endpoints']
        if not isinstance(endpoints,list) or len(endpoints)>10 or any(not isinstance(x,str) for x in endpoints):
            raise ManifestError('Invalid endpoints')
        if len(endpoints)!=len(set(endpoints)) or any(x not in FAMILY_ENDPOINTS.get(family,()) for x in endpoints):
            raise ManifestError('Unapproved endpoint')
        if known and not endpoints:
            raise ManifestError('Known family requires an approved endpoint')
        ops=model['operations']
        if not isinstance(ops,list) or not 1<=len(ops)<=30:
            raise ManifestError('Invalid operations')
        normalized=[]; seen=set()
        for op in ops:
            if not isinstance(op,dict) or set(op)!={'id','required_parameters'}:
                raise ManifestError('Invalid operation structure')
            name, params=op['id'],op['required_parameters']
            if not isinstance(name,str) or not NAME.fullmatch(name) or name in seen:
                raise ManifestError('Invalid operation identifier')
            if not isinstance(params,list) or len(params)>30 or any(not isinstance(p,str) or not PARAM.fullmatch(p) for p in params):
                raise ManifestError('Invalid required parameters')
            if len(params)!=len(set(params)):
                raise ManifestError('Duplicate parameters')
            if name not in FAMILY_OPERATIONS.get(family, ()):
                unsupported=True
            if name in FAMILY_OPERATIONS.get(family, ()):
                expected_type, expected_endpoint = OPERATION_ROUTES[family][name]
                if model['type'] != expected_type or expected_endpoint not in endpoints:
                    raise ManifestError('Operation endpoint or type mismatch')
            seen.add(name);normalized.append({'id':name,'required_parameters':list(params)})
        cleaned.append({'id':ident,'type':model['type'],'mode':model['mode'],
                        'endpoints':list(endpoints),'operations':normalized})
    return {'schema_version':1,'provider':provider,'adapter_family':family,'credential_ref':credential,
            'models':cleaned,'status':'METADATA_VALIDATED' if known and executable and not unsupported else 'NEEDS_ADAPTER',
            'live_verified':False}


def classify_error(error, *, submission=False):
    """Return a fixed safe category; never retry or infer rejection from ambiguous POST."""
    import asyncio
    import httpx
    from .providers import DefinitiveFailure, UnknownOutcome
    from .anymodel import AnyModelError
    from .submission import ProviderRefused
    if isinstance(error,UnsupportedAdapter): return 'NEEDS_ADAPTER'
    if isinstance(error,ManifestError): return 'CONFIG_ERROR'
    if isinstance(error,(ProviderRefused,DefinitiveFailure)): return 'REJECTED'
    if isinstance(error,UnknownOutcome) or submission: return 'UNKNOWN'
    if isinstance(error,AnyModelError):
        if error.status in (401,403): return 'AUTH_ERROR'
        if error.code in ('invalid_json','response_size','protocol'): return 'INVALID_RESPONSE'
        return 'UNAVAILABLE'
    if isinstance(error,httpx.HTTPStatusError) and error.response.status_code in (401,403): return 'AUTH_ERROR'
    if isinstance(error,(httpx.HTTPError,TimeoutError,asyncio.TimeoutError)): return 'UNAVAILABLE'
    if isinstance(error,(ValueError,TypeError)): return 'INVALID_RESPONSE'
    return 'UNAVAILABLE'
