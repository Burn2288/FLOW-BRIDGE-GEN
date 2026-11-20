"""Local-only HTTPS preview of the existing Mini App frontend, without a database."""
import argparse
import asyncio
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile

from aiohttp import web
from elevenbot.config import Config
from miniapp.backend.web import create_app


class NoDatabase:
    async def fetchval(self, *_args):
        raise RuntimeError('Preview has no database')


@web.middleware
async def preview_guard(request, handler):
    # Never simulate a user account, invoke a provider, or touch a database.
    if request.path.startswith('/api/'):
        return web.json_response({'error': 'preview_only'}, status=503,
                                 headers={'Cache-Control': 'no-store'})
    return await handler(request)


def preview_app():
    app = create_app(NoDatabase(), Config(token='local-preview-only', mode='mock',
                                           payments_enabled=False, generation_enabled=False))
    app.middlewares.insert(0, preview_guard)
    return app


def openssl_executable():
    exe = shutil.which('openssl')
    if exe:
        return exe
    if os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Git/usr/bin/openssl.exe'
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError('OpenSSL is required to create a temporary localhost certificate')


def temporary_tls(directory):
    cert, key = Path(directory) / 'localhost.pem', Path(directory) / 'localhost-key.pem'
    subprocess.run([openssl_executable(), 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-days', '1', '-keyout', str(key), '-out', str(cert),
                    '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    return context


async def serve(port):
    with tempfile.TemporaryDirectory(prefix='flowbridge-preview-') as directory:
        runner = web.AppRunner(preview_app(), access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, '127.0.0.1', port, ssl_context=temporary_tls(directory)).start()
            print(f'Local preview: https://localhost:{port}/', flush=True)
            print('Self-signed certificate; local preview only. Login and account data are unavailable.', flush=True)
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8443)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be in 1..65535')
    try:
        asyncio.run(serve(args.port))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
