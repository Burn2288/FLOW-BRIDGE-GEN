"""Metadata lifecycle; mock-only staging, with no provider I/O or dispatch changes."""
from copy import deepcopy
import hashlib
import json

from .discovery import DiscoveryError
from .provider_manifest import validate_manifest


class MockManifestProbe:
    """Deterministic offline staging probe; not evidence of live provider health."""
    def __init__(self, *, succeeds=True):
        self.succeeds = succeeds

    def check(self, manifest):
        return self.succeeds and bool(manifest['models'])


class ManifestLifecycle:
    """Process-local metadata snapshots; never dispatches or changes paid jobs."""
    def __init__(self, registry):
        self.registry = registry
        self._versions = {}
        self._active = {}
        self._previous = {}
        self._availability = {}

    def stage(self, manifest, probe):
        if type(probe) is not MockManifestProbe:
            raise DiscoveryError('Offline mock probe required')
        provider = manifest.get('provider') if isinstance(manifest, dict) else None
        value = validate_manifest(manifest, registered=self.registry.adapters,
                                  executable=isinstance(provider, str) and provider in self.registry.launches)
        if value['status'] == 'NEEDS_ADAPTER':
            return {'status': 'NEEDS_ADAPTER', 'version': None}
        if not probe.check(deepcopy(value)):
            return {'status': 'MOCK_FAILED', 'version': None}
        content = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
        version = hashlib.sha256(content).hexdigest()
        self._versions[(provider, version)] = deepcopy(value)
        return {'status': 'MOCK_VALIDATED', 'version': version}

    def activate(self, provider, version):
        if (provider, version) not in self._versions:
            raise DiscoveryError('Staged version not found')
        current = self._active.get(provider)
        if current != version:
            if current is not None:
                self._previous[provider] = current
            self._active[provider] = version
        self._availability.setdefault(provider, 'UNKNOWN')
        return version

    def rollback(self, provider):
        previous = self._previous.get(provider)
        if previous is None:
            raise DiscoveryError('No previous version')
        current = self._active[provider]
        self._active[provider] = previous
        self._previous[provider] = current
        return previous

    def pin(self, provider, model_id):
        version = self._active.get(provider)
        if version is None:
            raise DiscoveryError('No active version')
        manifest = self._versions[(provider, version)]
        model = next((m for m in manifest['models'] if m['id'] == model_id), None)
        if model is None:
            raise DiscoveryError('Model not found')
        return deepcopy({'provider': provider, 'version': version, 'model': model,
                         'credential_ref': manifest['credential_ref']})

    def observe_error(self, provider, error, *, submission=False):
        if provider not in self.registry.adapters:
            raise DiscoveryError('Provider not registered')
        category = self.registry.classify_error(error, submission=submission)
        # An uncertain operation is not evidence of provider-wide health.
        if category in ('UNAVAILABLE', 'AUTH_ERROR', 'CONFIG_ERROR', 'NEEDS_ADAPTER'):
            self._availability[provider] = category
        return category

    def availability(self, provider):
        if provider not in self.registry.adapters:
            raise DiscoveryError('Provider not registered')
        return self._availability.get(provider, 'UNKNOWN')
