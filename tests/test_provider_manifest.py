from copy import deepcopy

import httpx
import pytest
from elevenbot.aggregate import ProviderRegistry
from elevenbot.provider_manifest import ManifestError, UnsupportedAdapter
from elevenbot.providers import UnknownOutcome
from elevenbot.submission import ProviderRefused


class MockAdapter:
    async def collect(self):
        return {'models': [{'id': 'fixture/model', 'title': 'Fixture', 'operations': ['chat']}],
                'functions': [], 'scope': 'public_only'}


def manifest(provider, family, credential, endpoint):
    return {'schema_version': 1, 'provider': provider, 'adapter_family': family,
            'credential_ref': credential, 'models': [
                {'id': 'fixture/model', 'type': 'text', 'mode': 'sync',
                 'endpoints': [endpoint], 'operations': [{'id': 'chat', 'required_parameters': ['prompt']}]}
            ]}


@pytest.mark.parametrize('provider,credential,endpoint', [
    ('clodex', 'CLODEX_API_KEY', 'https://clodex.xyz/v1/chat/completions'),
    ('anymodel', 'ANYMODEL_API_KEY', 'https://anymodel.org/v1/chat/completions'),
])
async def test_existing_families_metadata_preserves_catalogue(provider, credential, endpoint):
    registry = ProviderRegistry()
    registry.register(provider, MockAdapter(), launch=object())
    before = await registry.collect()
    value = manifest(provider, provider, credential, endpoint)
    loaded = registry.load_manifest(value)
    assert loaded['status'] == 'METADATA_VALIDATED' and loaded['live_verified'] is False
    loaded['models'][0]['id'] = 'changed'
    assert registry.manifests[provider]['models'][0]['id'] == 'fixture/model'
    after = await registry.collect()
    assert before['version'] == after['version'] and before['models'] == after['models']


@pytest.mark.parametrize('mutate', [
    lambda m: m.update(schema_version=2),
    lambda m: m.update(schema_version=True),
    lambda m: m.update(unexpected='secret'),
    lambda m: m.update(credential_ref='actual-secret-value'),
    lambda m: m['models'][0].update(mode='arbitrary'),
    lambda m: m['models'][0].update(endpoints=['https://clodex.xyz.evil.invalid/v1/chat/completions']),
    lambda m: m['models'][0].update(endpoints=['https://clodex.xyz/v1/chat/completions?secret=1']),
    lambda m: m['models'][0].update(id='https://evil.invalid'),
    lambda m: m['models'][0]['operations'][0].update(required_parameters=['bad-param;exec']),
    lambda m: m.update(provider=[]),
])
def test_invalid_manifest_fails_closed_without_leaking_values(mutate, caplog):
    registry = ProviderRegistry(); registry.register('clodex', MockAdapter(), launch=object())
    value = manifest('clodex', 'clodex', 'CLODEX_API_KEY', 'https://clodex.xyz/v1/chat/completions')
    mutate(value)
    with pytest.raises(ManifestError) as error:
        registry.load_manifest(value)
    assert 'actual-secret-value' not in str(error.value) + caplog.text
    assert not registry.manifests


def test_unknown_family_and_protocol_never_become_executable():
    registry = ProviderRegistry(); registry.register('fixture', MockAdapter(), launch=object())
    value = manifest('fixture', 'unknown', None, 'unused')
    value['models'][0]['endpoints'] = []
    assert registry.load_manifest(value)['status'] == 'NEEDS_ADAPTER'
    bad=deepcopy(value);bad['models'][0]['endpoints']=['https://evil.invalid']
    with pytest.raises(ManifestError):registry.load_manifest(bad)
    registry.register('clodex', MockAdapter(), launch=object())
    value=manifest('clodex','clodex','CLODEX_API_KEY','https://clodex.xyz/v1/chat/completions')
    value['models'][0]['operations'][0]['id']='unknown.operation'
    assert registry.load_manifest(value)['status']=='NEEDS_ADAPTER'


@pytest.mark.parametrize('error,submission,category', [
    (UnknownOutcome('secret-api-key'), False, 'UNKNOWN'),
    (httpx.ReadTimeout('secret-api-key'), True, 'UNKNOWN'),
    (ValueError('secret-api-key'), True, 'UNKNOWN'),
    (ValueError('secret-api-key'), False, 'INVALID_RESPONSE'),
    (httpx.ConnectError('secret-api-key'), False, 'UNAVAILABLE'),
    (UnsupportedAdapter('secret-api-key'), False, 'NEEDS_ADAPTER'),
    (ManifestError('secret-api-key'), False, 'CONFIG_ERROR'),
    (ProviderRefused('secret-api-key'), True, 'REJECTED'),
])
def test_safe_error_categories_preserve_uncertainty(error, submission, category, caplog):
    assert ProviderRegistry.classify_error(error, submission=submission) == category
    assert 'secret-api-key' not in caplog.text


def test_read_auth_error_and_ambiguous_submission():
    response = httpx.Response(401, request=httpx.Request('GET', 'https://fixture.invalid'))
    error = httpx.HTTPStatusError('secret-api-key', request=response.request, response=response)
    assert ProviderRegistry.classify_error(error) == 'AUTH_ERROR'
    assert ProviderRegistry.classify_error(error, submission=True) == 'UNKNOWN'


@pytest.mark.parametrize('family,mode', [('clodex','sync'), ('anymodel','async')])
async def test_mock_family_submission_failure_never_retries(family, mode):
    calls = []
    def response(request):
        calls.append(request)
        raise httpx.ReadTimeout('fixture-secret-do-not-log', request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        try:
            await client.post('https://fixture.invalid/generate')
        except httpx.ReadTimeout as error:
            outcome = ProviderRegistry.classify_error(error, submission=True)
    assert outcome == 'UNKNOWN' and len(calls) == 1
    registry=ProviderRegistry();registry.register(family, MockAdapter(), launch=object())
    endpoint = ('https://clodex.xyz/v1/chat/completions' if family=='clodex'
                else 'https://anymodel.org/v1/chat/completions')
    credential = 'CLODEX_API_KEY' if family=='clodex' else 'ANYMODEL_API_KEY'
    value = manifest(family, family, credential, endpoint)
    value['models'][0]['mode'] = mode
    assert registry.load_manifest(value)['models'][0]['mode'] == mode


def test_anymodel_categories_do_not_assume_submission_rejected():
    from elevenbot.anymodel import AnyModelError
    error = AnyModelError('fixture-secret', status=401, code='http_401')
    assert ProviderRegistry.classify_error(error) == 'AUTH_ERROR'
    assert ProviderRegistry.classify_error(error, submission=True) == 'UNKNOWN'
    assert ProviderRegistry.classify_error(AnyModelError('secret', code='invalid_json')) == 'INVALID_RESPONSE'


def test_known_operation_requires_matching_type_and_route():
    registry = ProviderRegistry()
    registry.register('clodex', MockAdapter(), launch=object())
    value = manifest('clodex', 'clodex', 'CLODEX_API_KEY', 'https://clodex.xyz/v1/chat/completions')
    value['models'][0]['type'] = 'image'
    with pytest.raises(ManifestError):
        registry.load_manifest(value)
    value['models'][0]['type'] = 'text'
    value['models'][0]['endpoints'] = ['https://clodex.xyz/v1/images/generations']
    with pytest.raises(ManifestError):
        registry.load_manifest(value)
