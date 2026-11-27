import json
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer
from elevenbot.config import Config
from miniapp.backend.web import create_app
from scripts.openapi_viewer import app, render


def test_contract_matches_existing_http_routes():
    spec = json.loads(Path('miniapp/openapi.json').read_text(encoding='utf8'))
    assert spec['openapi'] == '3.1.0'
    real = create_app(object(), Config(token='test'))
    actual = {(route.method, route.resource.canonical) for route in real.router.routes()
              if route.method not in ('HEAD',) and (route.resource.canonical.startswith('/api/')
                                                   or route.resource.canonical == '/healthz')}
    documented = {(method.upper(), path) for path, methods in spec['paths'].items() for method in methods}
    assert actual == documented
    assert all('401' in op['responses'] for path, methods in spec['paths'].items()
               for method, op in methods.items() if path.startswith('/api/'))
    assert spec['paths']['/api/v1/wallet']['get']['security'] == [{'bearerAuth': []}]
    assert spec['paths']['/api/v1/admin/capabilities']['get']['security'] == [{'bearerAuth': []}]
    assert 'Mini App API' in render(spec)


async def test_viewer_serves_schema_and_html():
    async with TestClient(TestServer(app())) as client:
        response = await client.get('/')
        assert response.status == 200 and '/api/v1/wallet' in await response.text()
        response = await client.get('/openapi.json')
        assert response.status == 200 and (await response.json())['openapi'] == '3.1.0'

async def test_existing_http_rejects_unauthenticated_access():
    class NoDatabase:
        def acquire(self):
            raise AssertionError('unauthenticated request reached the database')
    async with TestClient(TestServer(create_app(NoDatabase(), Config(token='fixture')))) as client:
        for path in ('/api/v1/catalogue', '/api/v1/wallet', '/api/v1/settings', '/api/v1/works', '/api/v1/referral/finances', '/api/v1/admin/capabilities'):
            assert (await client.get(path)).status == 401
        assert (await client.post('/api/v1/session', json={'initData': 'forged'})).status == 401
