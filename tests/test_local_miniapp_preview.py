import ssl

from aiohttp.test_utils import TestClient, TestServer

from scripts.local_miniapp_preview import preview_app, temporary_tls


async def test_local_https_preview_serves_existing_frontend_without_accounts(tmp_path):
    server = TestServer(preview_app(), host='127.0.0.1', scheme='https')
    await server.start_server(ssl=temporary_tls(tmp_path))
    async with TestClient(server) as client:
        response = await client.get('/', ssl=False)
        assert response.status == 200
        assert 'data-panel="catalogue"' in await response.text()
        assert (await client.get('/assets/app.js', ssl=False)).status == 200
        assert (await client.get('/assets/style.css', ssl=False)).status == 200
        response = await client.post('/api/v1/session', json={'initData': 'fixture'}, ssl=False)
        assert response.status == 503 and await response.json() == {'error': 'preview_only'}
        response = await client.get('/api/v1/wallet', ssl=False)
        assert response.status == 503
        assert (await client.get('/healthz', ssl=False)).status == 503


def test_certificate_is_local_only(tmp_path):
    context = temporary_tls(tmp_path)
    assert isinstance(context, ssl.SSLContext)
    assert (tmp_path / 'localhost.pem').exists()
