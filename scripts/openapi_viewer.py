"""Show the existing Mini App API contract locally, without connecting to a database."""
import argparse
import html
import json
from pathlib import Path
from aiohttp import web

SPEC = Path(__file__).resolve().parents[1] / 'miniapp' / 'openapi.json'


def render(spec):
    rows = []
    for path, methods in spec['paths'].items():
        for method, item in methods.items():
            errors = ', '.join(code for code in item['responses'] if code.startswith(('4', '5')))
            rows.append('<tr><td>' + html.escape(method.upper()) + '</td><td><code>' +
                        html.escape(path) + '</code></td><td>' + html.escape(item['summary']) +
                        '</td><td>' + html.escape(errors or '—') + '</td></tr>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>API FLOW</title>'
            '<style>body{font:16px sans-serif;max-width:960px;margin:2em auto;padding:1em}'
            'table{border-collapse:collapse;width:100%}td,th{padding:.6em;border:1px solid #bbb;text-align:left}'
            '</style><h1>Mini App API</h1><p>Действующие маршруты и ошибки доступа. '
            'Административные операции не включены.</p><p><a href="/openapi.json">OpenAPI JSON</a></p>'
            '<table><thead><tr><th>Метод</th><th>Путь</th><th>Назначение</th><th>Ошибки</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></html>')


def app():
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    site = web.Application()
    async def index(_request):
        return web.Response(text=render(spec), content_type='text/html')
    async def schema(_request):
        return web.json_response(spec)
    site.router.add_get('/', index)
    site.router.add_get('/openapi.json', schema)
    return site


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8092)
    args = parser.parse_args()
    web.run_app(app(), host='127.0.0.1', port=args.port, print=None)
