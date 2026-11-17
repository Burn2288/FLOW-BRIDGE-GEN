"""Read the bot's Docker Compose trace from a loopback-only browser panel."""

import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765
FIELDS = (
    'request_id', 'stage', 'model', 'operation', 'mode', 'method', 'endpoint',
    'request_fields', 'response_format', 'status', 'content_type', 'elapsed_ms',
    'bytes', 'json_type', 'has_error', 'error_code', 'data_items', 'has_base64',
    'base64_chars', 'has_url', 'has_choices', 'has_candidates', 'has_task_id',
    'image_bytes', 'error_type', 'failed_at',
)


def read_events(output):
    events = []
    for line in output.splitlines():
        timestamp, _, payload = line.partition(' ')
        try:
            event = json.loads(payload)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('event') == 'interaction':
            events.append({
                'time': timestamp,
                **{field: event[field] for field in FIELDS if field in event},
            })
    return sorted(events, key=lambda event: event['time'])


PAGE = '''<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>DarkFlow · Мониторинг генерации</title>
<style>
body{font:16px system-ui;color:#e7edf5;background:#101722;margin:32px}
h1{font-size:26px}
section{background:#1b2738;border-radius:12px;padding:16px}
article{border-top:1px solid #3c4d64;padding:12px 0}
h3{font-size:16px;margin:0;color:#e7edf5;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;margin-bottom:0}
</style>
<h1>DarkFlow · Мониторинг генерации</h1>
<p id="status">Загружаем журнал Docker…</p>
<main><section>
<h2>Общий журнал</h2>
<label>Фильтр <input id="filter" type="search" placeholder="Модель, операция или ID"></label>
<div id="details"></div>
</section></main>
<script>
const labels = {
 input_validated:'Запрос принят', reserved:'Запрос зарегистрирован',
 reservation_failed:'Ошибка регистрации запроса', duplicate:'Повторный запрос',
 http_start:'Отправка в CLODEX', http_headers:'Получены HTTP-заголовки',
 http_body_received:'Получен ответ', response_shape:'Формат ответа',
 decode_ok:'Результат прочитан', decode_failed:'Не удалось прочитать результат',
 image_download_start:'Скачивание изображения', image_download_headers:'Ответ сервера изображения',
 image_download_ok:'Изображение скачано', image_download_failed:'Ошибка скачивания изображения',
 generation_failed:'Генерация завершилась ошибкой', image_saved:'Картинка сохранена',
 result_notified:'Пользователь уведомлён', save_failed:'Ошибка сохранения',
 http_error:'Ошибка HTTP', timeout:'Тайм-аут', network_error:'Ошибка сети',
 invalid_json:'Некорректный JSON', http_body_too_large:'Слишком большой ответ',
 queued:'В очереди', worker_started:'Worker взял задачу', audio_received:'Аудио получено',
 audio_saved:'Аудио сохранено', work_completed:'Работа завершена',
 work_uncertain:'Результат не подтверждён', worker_failed:'Ошибка worker',
 provider_response_rejected:'Ответ провайдера отклонён',
 operation_unavailable:'Запуск операции недоступен', preview_only:'Только предпросмотр запроса',
 preview_failed:'Не удалось подготовить запрос'
};
const statusLine = document.querySelector('#status');
const details = document.querySelector('#details');
const filter = document.querySelector('#filter');
let events = [];
let lastPayload;
function renderLog() {
 const query = filter.value.trim().toLowerCase();
 const requests = new Map();
 for (const event of events) {
   const info = requests.get(event.request_id) || {};
   if (event.model) info.model = event.model;
   if (event.operation) info.operation = event.operation;
   requests.set(event.request_id, info);
 }
 const entries = document.createDocumentFragment();
 for (const event of events) {
   const {time, stage, request_id, model, operation, ...fields} = event;
   const info = requests.get(request_id);
   const label = labels[stage] || stage;
   if (![request_id, info.model, info.operation, stage, label]
       .some(value => String(value ?? '').toLowerCase().includes(query))) continue;
   const article = document.createElement('article');
   const heading = document.createElement('h3');
   heading.textContent = [new Date(time).toLocaleString(), label, '#' + request_id,
     model || info.model, operation || info.operation].filter(Boolean).join(' · ');
   article.append(heading);
   if (Object.keys(fields).length) {
     const data = document.createElement('pre');
     data.textContent = JSON.stringify(fields, null, 2);
     article.append(data);
   }
   entries.append(article);
 }
 details.replaceChildren(entries);
 if (!details.firstChild) details.textContent = query
   ? 'По фильтру ничего не найдено.' : 'В журнале пока нет событий.';
}
filter.addEventListener('input', renderLog);
async function refresh() {
 try {
   const response = await fetch('/events', {cache:'no-store'});
   if (!response.ok) throw new Error();
   const payload = await response.text();
   if (payload !== lastPayload) {
     events = JSON.parse(payload);
     lastPayload = payload;
     renderLog();
   }
   statusLine.textContent = 'Событий: ' + events.length + ' · Обновлено ' + new Date().toLocaleTimeString();
 } catch {
   statusLine.textContent = 'Журнал недоступен. Проверьте Docker и запуск контейнера bot.';
 } finally {
   setTimeout(refresh, 3000);
 }
}
refresh();
</script></html>'''


class Monitor(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{PORT}':
            self.send_error(403)
            return
        if self.path == '/':
            body = PAGE.encode()
            content_type = 'text/html; charset=utf-8'
        elif self.path == '/events':
            try:
                logs = subprocess.run(
                    ['docker', 'compose', 'logs', '--no-color', '--no-log-prefix',
                     '--timestamps', 'bot', 'worker'],
                    cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace',
                    timeout=8, check=True,
                )
            except (OSError, subprocess.SubprocessError):
                self.send_error(503)
                return
            body = json.dumps(read_events(logs.stdout)).encode()
            content_type = 'application/json'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


if __name__ == '__main__':
    with HTTPServer(('127.0.0.1', PORT), Monitor) as server:
        print(f'DarkFlow monitor: http://127.0.0.1:{PORT}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
