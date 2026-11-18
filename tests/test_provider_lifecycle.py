"""Offline metadata lifecycle tests; no paid provider or database mutation."""
import logging
from copy import deepcopy

import httpx
import pytest

from elevenbot.aggregate import ProviderRegistry
from elevenbot.discovery import DiscoveryError
from elevenbot.provider_lifecycle import MockManifestProbe
from test_provider_manifest import MockAdapter, manifest


def configured(provider='clodex'):
    registry = ProviderRegistry()
    registry.register(provider, MockAdapter(), launch=object())
    credential = {'clodex': 'CLODEX_API_KEY', 'anymodel': 'ANYMODEL_API_KEY'}[provider]
    domain = {'clodex': 'clodex.xyz', 'anymodel': 'anymodel.org'}[provider]
    value = manifest(provider, provider, credential, f'https://{domain}/v1/chat/completions')
    return registry, value


def test_staging_activation_pinning_and_rollback_preserve_job_snapshot():
    registry, initial = configured()
    lifecycle = registry.lifecycle
    old = lifecycle.stage(initial, MockManifestProbe())['version']
    lifecycle.activate('clodex', old)
    pinned = lifecycle.pin('clodex', 'fixture/model')
    updated = deepcopy(initial)
    updated['models'][0]['operations'][0]['required_parameters'].append('temperature')
    new = lifecycle.stage(updated, MockManifestProbe())['version']
    assert new != old
    lifecycle.activate('clodex', new)
    assert lifecycle.pin('clodex', 'fixture/model')['version'] == new
    assert pinned['version'] == old and pinned['model']['operations'][0]['required_parameters'] == ['prompt']
    pinned['model']['id'] = 'mutated'
    assert lifecycle.rollback('clodex') == old
    assert lifecycle.pin('clodex', 'fixture/model')['model']['id'] == 'fixture/model'


def test_rejected_staging_never_activates_and_unsupported_stays_needs_adapter():
    registry, value = configured()
    assert registry.lifecycle.stage(value, MockManifestProbe(succeeds=False))['status'] == 'MOCK_FAILED'
    with pytest.raises(DiscoveryError):
        registry.lifecycle.pin('clodex', 'fixture/model')
    value['models'][0]['operations'][0]['id'] = 'unknown.operation'
    assert registry.lifecycle.stage(value, MockManifestProbe()) == {'status': 'NEEDS_ADAPTER', 'version': None}
    with pytest.raises(DiscoveryError):
        registry.lifecycle.stage(value, object())


def test_provider_observations_are_isolated_and_do_not_leak_secrets(caplog):
    registry, _ = configured()
    registry.register('anymodel', MockAdapter(), launch=object())
    with caplog.at_level(logging.DEBUG):
        error = httpx.ConnectError('secret-key-token')
        assert registry.lifecycle.observe_error('clodex', error) == 'UNAVAILABLE'
        assert registry.lifecycle.availability('clodex') == 'UNAVAILABLE'
        assert registry.lifecycle.availability('anymodel') == 'UNKNOWN'
        assert registry.lifecycle.observe_error('anymodel', error, submission=True) == 'UNKNOWN'
        assert registry.lifecycle.availability('anymodel') == 'UNKNOWN'
    assert 'secret-key-token' not in caplog.text


def test_catalogue_objects_and_execution_registry_are_not_replaced():
    registry, value = configured('anymodel')
    original = registry.launches['anymodel']
    version = registry.lifecycle.stage(value, MockManifestProbe())['version']
    registry.lifecycle.activate('anymodel', version)
    assert registry.launches['anymodel'] is original
    with pytest.raises(DiscoveryError):
        registry.lifecycle.rollback('anymodel')


async def test_inflight_mock_keeps_snapshot_on_failure_and_rollback():
    import asyncio
    registry, first = configured()
    lifecycle = registry.lifecycle
    old = lifecycle.stage(first, MockManifestProbe())['version']
    lifecycle.activate('clodex', old)
    snapshot = lifecycle.pin('clodex', 'fixture/model')
    sent = []
    started, finish = asyncio.Event(), asyncio.Event()

    async def mock_inflight():
        sent.append(snapshot['version'])
        started.set()
        await finish.wait()
        return snapshot['version']

    task = asyncio.create_task(mock_inflight())
    await started.wait()
    updated = deepcopy(first)
    updated['models'][0]['operations'][0]['required_parameters'].append('temperature')
    new = lifecycle.stage(updated, MockManifestProbe())['version']
    lifecycle.activate('clodex', new)
    assert lifecycle.observe_error('clodex', httpx.ReadTimeout('redacted'), submission=True) == 'UNKNOWN'
    assert lifecycle.rollback('clodex') == old
    finish.set()
    assert await task == old
    assert sent == [old]


def test_failed_stage_does_not_replace_active_version():
    registry, value = configured()
    lifecycle = registry.lifecycle
    version = lifecycle.stage(value, MockManifestProbe())['version']
    lifecycle.activate('clodex', version)
    changed = deepcopy(value)
    changed['models'][0]['mode'] = 'async'
    assert lifecycle.stage(changed, MockManifestProbe(succeeds=False))['status'] == 'MOCK_FAILED'
    assert lifecycle.pin('clodex', 'fixture/model')['version'] == version
    with pytest.raises(DiscoveryError):
        lifecycle.activate('clodex', 'unvalidated')
