"""Drive the existing local Compose DEV profile through both client interfaces."""

import argparse
import asyncio
import hashlib
import hmac
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID, uuid4

import httpx
from playwright.async_api import TimeoutError as BrowserTimeout, async_playwright, expect


@dataclass(frozen=True)
class Studio:
    key: str
    operation: str
    model: str
    prompt_label: str
    work_route: str
    telegram_method: str
    media_tag: str


STUDIOS = (
    Studio('image', 'images.generate', 'flux-schnell', 'Описание изображения', 'image', 'sendphoto', 'img'),
    Studio('video', 'video', 'clodex-video/veo-3.1', 'Описание видео', 'video', 'sendvideo', 'video'),
    Studio('speech', 'audio.speech', 'eleven_v4', 'Текст для озвучки', 'get', 'sendaudio', 'audio'),
    Studio('music', 'audio.generate', 'clodex-video/music-v1', 'Описание трека', 'musicwork', 'sendaudio', 'audio'),
)
FIXTURE_TOKEN = '123456:' + 'fixture_' * 5
TIMEOUT = 45


def signed_launch(chat):
    fields = {
        'auth_date': str(int(time.time())),
        'query_id': 'runtime-matrix-' + uuid4().hex,
        'user': json.dumps({'id': chat}),
    }
    message = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
    key = hmac.digest(b'WebAppData', FIXTURE_TOKEN.encode(), 'sha256')
    return urlencode(fields | {'hash': hmac.new(key, message.encode(), hashlib.sha256).hexdigest()})


class Telegram:
    def __init__(self, client):
        self.client = client

    async def replies(self, after=0):
        response = await self.client.get('/fixture/replies', params={'after': after})
        response.raise_for_status()
        return response.json()['replies']

    async def update(self, chat, **fields):
        existing = await self.replies()
        last = existing[-1]['sequence'] if existing else 0
        response = await self.client.post('/fixture/updates', json={'chat': chat, **fields})
        response.raise_for_status()
        return last

    async def wait(self, chat, after, select, label):
        recent = []
        for _ in range(TIMEOUT * 5):
            recent = [event for event in await self.replies(after) if event['chat'] == chat]
            for event in reversed(recent):
                if value := select(event):
                    return value
            await asyncio.sleep(.2)
        snippets = [event.get('text', '')[:110] for event in recent[-4:]]
        raise AssertionError(f'Telegram {chat}: missing {label}; last replies: {snippets}')

    async def button(self, chat, after, match):
        def select(event):
            for row in (event.get('reply_markup') or {}).get('inline_keyboard', ()):
                for button in row:
                    callback = button.get('callback_data', '')
                    if callback and re.search(match, callback):
                        return event['message_id'], callback
        return await self.wait(chat, after, select, match)

    async def tap(self, chat, after, match):
        message_id, callback = await self.button(chat, after, match)
        return await self.update(chat, callback=callback, message_id=message_id)

    async def start(self, chat, *, admin=False):
        after = await self.update(chat, text='/start')
        def start_reply(event):
            value = event.get('reply_markup') or {}
            for row in value.get('inline_keyboard', ()):
                for button in row:
                    if button.get('callback_data', '').startswith('accept:'):
                        return event['message_id'], button['callback_data']
            if value.get('keyboard'):
                return 'ready'
        consent = await self.wait(chat, after, start_reply, 'welcome or consent')
        if consent != 'ready':
            message_id, callback = consent
            after = await self.update(chat, callback=callback, message_id=message_id)
            await self.wait(chat, after, lambda event: (event.get('reply_markup') or {}).get('keyboard'), 'main menu')
        if admin:
            after = await self.update(chat, text='/admin')
            def admin_reply(event):
                if 'паролем Admin Edition' in (event.get('text') or ''):
                    return event['message_id']
                for row in (event.get('reply_markup') or {}).get('inline_keyboard', ()):
                    if any(button.get('callback_data', '').startswith('provider:') for button in row):
                        return 'ready'
            prompt = await self.wait(chat, after, admin_reply, 'admin menu or password prompt')
            if isinstance(prompt, int):
                after = await self.update(chat, text='fixture-password', reply_to=prompt)
                assert await self.wait(chat, after, admin_reply, 'admin menu') == 'ready'

    async def grant_music(self, chat):
        response = await self.client.post('/fixture/music-grant', json={'chat': chat})
        response.raise_for_status()
        assert response.json()['granted'] >= 0

    async def start_job(self, studio, chat, prompt):
        after = await self.update(chat, text='🌐 Агрегаторы')
        after = await self.tap(chat, after, r'^provider:')
        if studio.key == 'music':
            after = await self.tap(chat, after, r'^music$')
            await self.tap(chat, after, r'^musicprompt$')
        else:
            after = await self.tap(chat, after, rf'^slist:current:{studio.key}:0$')
            after = await self.tap(chat, after, rf'^smodel:.*:{studio.key}:')
            after = await self.tap(chat, after, rf'^srun:.*:{studio.key}:.*:[0-9]+$')
            if studio.key == 'speech':
                await self.tap(chat, after, r'^voice:')
        after = await self.update(chat, text=prompt)
        message_id, callback = await self.button(chat, after, r'^(amconfirm|musicconfirm):')
        await self.update(chat, callback=callback, message_id=message_id)
        return UUID(callback.rsplit(':', 1)[-1])

    async def check_result(self, studio, chat, work_id, digest):
        after = await self.update(chat, text='📁 Мои работы')
        for _ in range(4):
            pattern = rf'^{studio.work_route}:{work_id}$'
            message_id, callback = await self.button(chat, after, pattern + r'|^history:[1-9][0-9]*$')
            if re.search(pattern, callback):
                after = await self.update(chat, callback=callback, message_id=message_id)
                await self.wait(chat, after, lambda event: event['method'] == studio.telegram_method
                                and event['media_sha256'] == digest, 'matching delivered media')
                return
            after = await self.update(chat, callback=callback, message_id=message_id)
        raise AssertionError(f'Telegram result {work_id} missing from the first four library pages')


async def open_client(context, base, chat, *, accept_terms=False):
    launch = signed_launch(chat)
    async def sdk(route):
        await route.fulfill(content_type='application/javascript', body=
            'window.Telegram={WebApp:{ready(){},initData:' + json.dumps(launch) + '}};')
    await context.route('https://telegram.org/js/telegram-web-app.js', sdk)
    page = await context.new_page()
    async with page.expect_response(base + '/api/v1/session') as session:
        await page.goto(base)
    response = await session.value
    if accept_terms and response.status == 428:
        async with page.expect_response(base + '/api/v1/session') as accepted:
            await page.get_by_role('button', name='Принять условия и продолжить').click()
        response = await accepted.value
    assert response.status == 200
    await expect(page.get_by_label('Студия')).to_be_enabled()
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    return page


async def start_miniapp_job(page, studio, prompt):
    await page.get_by_role('button', name='Каталог', exact=True).click()
    await page.get_by_label('Студия').select_option(studio.operation)
    if studio.key == 'speech':
        await page.get_by_role('button', name='Выбрать голос', exact=True).click()
    elif studio.key in ('video', 'music'):
        name = 'Veo 3.1' if studio.key == 'video' else 'Leonardo Music'
        await page.get_by_role('button', name=re.compile('^Выбрать ' + re.escape(name))).first.click()
    await page.get_by_label(studio.prompt_label).fill(prompt)
    panel = page.locator('#models > li:visible').filter(has=page.get_by_label(studio.prompt_label))
    async with page.expect_response(lambda response: response.url.endswith('/api/v1/quotes')) as quote:
        await panel.get_by_role('button', name='Рассчитать стоимость').click()
    quote_response = await quote.value
    assert quote_response.status == 201, f'quote status {quote_response.status}'
    offered = await quote_response.json()
    async with page.expect_response(lambda response: response.url.endswith('/api/v1/jobs')
                                    and response.request.method == 'POST') as job:
        await panel.get_by_role('button', name=re.compile('^Подтвердить за ')).click()
    confirmed = await job.value
    assert confirmed.status == 201, f'confirm status {confirmed.status}'
    result = await confirmed.json()
    assert result['id'] == offered['quote_id']
    return UUID(result['id'])


async def read_result(project, job):
    job = UUID(str(job))
    sql = f"""
    SELECT jsonb_build_object(
        'model', q.model_id, 'prompt', q.request->>'prompt',
        'chat', identity.external_id, 'price', q.price->>'total',
        'parameters', q.request->'params', 'quote_state', q.state,
        'dispatch_state', dispatch.state,
        'work_state', CASE WHEN image.id IS NOT NULL OR speech.audio IS NOT NULL THEN 'succeeded'
                           ELSE coalesce(video.status, music.status) END,
        'work_id', coalesce(image.id,
            CASE WHEN video.status='succeeded' AND video.video IS NOT NULL THEN video.id END,
            CASE WHEN speech.audio IS NOT NULL THEN speech.id END,
            CASE WHEN music.mp3 IS NOT NULL THEN music.id END),
        'capture', (SELECT count(*) FROM ledger WHERE task_quote_id=q.id AND kind='task_capture'),
        'grant', (SELECT coalesce(sum(da), 0) FROM clodex_music_ledger
             WHERE user_id=q.user_id AND kind='credit' AND provider=q.provider),
        'grant_capture', (SELECT count(*) FROM clodex_music_ledger WHERE quote_id=q.id AND kind='capture')
    ) FROM task_price_quotes q
    JOIN identities identity ON identity.user_id=q.user_id AND identity.platform='telegram'
    LEFT JOIN task_dispatch dispatch ON dispatch.quote_id=q.id
    LEFT JOIN image_works image ON q.operation='images.generate' AND image.update_id=q.update_id AND image.user_id=q.user_id
    LEFT JOIN video_jobs video ON video.id=q.id AND video.user_id=q.user_id
    LEFT JOIN task_speech_works speech ON speech.id=q.id AND speech.user_id=q.user_id
    LEFT JOIN clodex_music_jobs music ON music.id=q.id AND music.user_id=q.user_id
    WHERE q.id='{job}'::uuid
    """
    deadline = time.monotonic() + TIMEOUT
    evidence = {}
    while time.monotonic() < deadline:
        process = await asyncio.create_subprocess_exec(
            'docker', 'compose', '-f', 'compose.dev.yaml', '-p', project,
            'exec', '-T', 'db', 'psql', '-X', '-U', 'postgres', '-d', 'flowbridge_dev', '-Atqc', sql,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode:
            raise AssertionError(stderr.decode().strip())
        evidence = json.loads(stdout or '{}')
        if evidence.get('work_id') and evidence['quote_state'] == 'accepted' and (
            evidence['capture'] or evidence['grant_capture']
        ):
            return evidence
        await asyncio.sleep(.25)
    raise AssertionError(f'No stored result or settlement for {job}: {evidence}')


async def verify_browser_result(page, studio, evidence, screenshot, *, job=None):
    await page.get_by_role('button', name='Мои работы', exact=True).click()
    if job:
        await page.get_by_role('button', name='Открыть задание ' + str(job), exact=True).click()
        await expect(page.locator('#job-status')).to_have_text('Завершено')
        await page.get_by_role('button', name='Показать результат', exact=True).click()
    artifact = page.locator('#work-' + evidence['work_id'])
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    await artifact.get_by_role('button', name='Просмотр', exact=True).click()
    media = artifact.locator(studio.media_tag)
    await expect(media).to_be_visible()
    if studio.media_tag == 'img':
        await expect(media).to_have_js_property('complete', True)
        assert await media.evaluate('image => image.naturalWidth') > 0
    else:
        await page.wait_for_function(
            'media => media.readyState >= 1', arg=await media.element_handle(), timeout=8000,
        )
    if screenshot:
        await artifact.screenshot(path=screenshot)
    async with page.expect_download() as download:
        await artifact.get_by_role('button', name='Скачать', exact=True).click()
    path = await (await download.value).path()
    content = path.read_bytes()
    assert content
    return hashlib.sha256(content).hexdigest()


async def run(args):
    args.artifacts.mkdir(parents=True, exist_ok=True)
    base = f'http://127.0.0.1:{args.miniapp_port}'
    fixture = f'http://127.0.0.1:{args.fixture_port}'
    chromium = shutil.which('chromium') or shutil.which('google-chrome')
    if not chromium:
        raise SystemExit('Chromium or Google Chrome is required.')
    results = []
    async with httpx.AsyncClient(base_url=fixture, timeout=TIMEOUT, trust_env=False) as client, async_playwright() as pw:
        telegram = Telegram(client)
        browser = await pw.chromium.launch(executable_path=chromium)
        try:
            for studio in STUDIOS:
                for origin in ('telegram', 'miniapp'):
                    chat = 101 if studio.key == 'image' else 100
                    if studio.key == 'music' and origin == 'miniapp':
                        chat = 102
                    label = f'{origin}-{studio.key}'
                    if args.route and label != args.route:
                        continue
                    prompt = f'Functional matrix {label} {uuid4().hex[:8]}'
                    context = await browser.new_context(viewport={'width': 360, 'height': 800})
                    job = None
                    try:
                        await telegram.start(chat, admin=chat != 101)
                        if studio.key == 'music':
                            await telegram.grant_music(chat)
                        page = await open_client(context, base, chat)
                        job = await (telegram.start_job(studio, chat, prompt) if origin == 'telegram'
                                     else start_miniapp_job(page, studio, prompt))
                        evidence = await read_result(args.project, job)
                        assert (evidence['model'], evidence['chat'], evidence['prompt']) == (studio.model, chat, prompt)
                        if studio.key == 'music':
                            assert evidence['capture'] == 0 and evidence['grant_capture'] == 1 and evidence['grant'] > 0
                        else:
                            assert evidence['capture'] == 1 and evidence['grant_capture'] == 0
                        digest = await verify_browser_result(
                            page, studio, evidence, args.artifacts / f'{label}.png', job=job,
                        )
                        await telegram.check_result(studio, chat, evidence['work_id'], digest)
                        result = {'route': label, 'status': 'passed', 'job': str(job), 'media_sha256': digest, **evidence}
                    except (AssertionError, BrowserTimeout, httpx.HTTPError) as error:
                        result = {'route': label, 'status': 'failed', 'chat': chat, 'prompt': prompt,
                                  'job': str(job) if job else None, 'error': str(error)}
                    finally:
                        await context.close()
                    results.append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            await browser.close()
    report = args.artifacts / (f'{args.route}.json' if args.route else 'matrix.json')
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    passed = sum(item['status'] == 'passed' for item in results)
    print(f'STUDIO_MATRIX={passed}/{len(results)}')
    return 0 if passed == len(results) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, help='Dedicated running DEV Compose project')
    parser.add_argument('--fixture-port', type=int, default=8081)
    parser.add_argument('--miniapp-port', type=int, default=8091)
    parser.add_argument('--route', choices=[f'{origin}-{studio.key}' for studio in STUDIOS
                                         for origin in ('telegram', 'miniapp')])
    parser.add_argument('--artifacts', type=Path, required=True)
    return asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
