"""MA-01 browser journey on the running OP-01 HTTPS fixture."""
import base64
import hashlib
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from elevenbot.aggregate import make_snapshot
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from miniapp.tests.test_miniapp import signed
from test_admin_access import event
from test_ui import Bot
from elevenbot.telegram import TelegramApp


async def check_miniapp_journey(telegram, owner, tester, base, cert, client, pending_jobs):
    from playwright.async_api import async_playwright, expect

    cfg = telegram.cfg
    models = [dict(provider='clodex', id='fixture/image', title='MA-01 Image',
                   availability='key_available', operations=['images.generate'])]
    models.append(dict(provider='clodex', id='flux-schnell', title='FLUX Schnell', availability='key_available',
                       operations=['images.generate'], protocols=['image-generation']))
    await telegram.pricing.set_tariff(owner, 100, 'clodex', 'flux-schnell', 'images.generate', {'n': 1},
                                      basis='request', unit='darkflow_token', amount='10', expires=None, evidence='fixture')
    SnapshotStore(cfg.catalogue_path).write(make_snapshot(
        models, [], [dict(provider='clodex', scope='key_available')]))
    await telegram.pool.execute("INSERT INTO approved_models VALUES('clodex','fixture/image','images.generate','Image')")
    banner = Path(__file__).resolve().parents[2] / 'miniapp/frontend/assets/darkflow-banner.png'
    profiles = [(100, owner, 1200, 'work-A', MOCK_IMAGE), (101, tester, 375, 'work-B', banner.read_bytes())]
    work_ids = []
    for external, user, credits, model, content in profiles:
        async with telegram.pool.acquire() as conn, conn.transaction():
            await telegram.svc.movement(conn, user, 'live', model, 'pilot_grant', credits, 0)
        work_ids.append(await telegram.svc.save_image_work(
            user, external, model, 'fixture', SimpleNamespace(image=content, filename='test.png')))

    # Trust only the ephemeral OP-01 certificate key in the test browser.
    pubkey = subprocess.check_output(['openssl', 'x509', '-in', str(cert), '-noout', '-pubkey'])
    der = subprocess.check_output(['openssl', 'pkey', '-pubin', '-outform', 'DER'], input=pubkey)
    pin = base64.b64encode(hashlib.sha256(der).digest()).decode()
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    assert chrome, 'The HTTPS browser profile requires Chrome or Chromium'
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=chrome, args=['--ignore-certificate-errors-spki-list=' + pin])
        try:
            for external, _, credits, model, content in profiles:
                context = await browser.new_context()
                page = await context.new_page()
                # Only the Telegram host bridge is simulated. The page and every
                # application request go through Caddy to the real backend.
                launch_data = signed(cfg.token, external, query_id='ma01-browser')
                async def sdk(route):
                    await route.fulfill(content_type='application/javascript', body=
                        'window.Telegram={WebApp:{ready(){},sendData(){},initData:' + json.dumps(launch_data) + '}};')
                await context.route('https://telegram.org/js/telegram-web-app.js', sdk)
                keyboard = await telegram.reply_menu(external)
                keyboard_url = keyboard.keyboard[0][0].web_app.url
                await telegram.handle(event(1000 + external, '/miniapp', chat=external))
                inline_url = telegram.bot.sent[-1][1].inline_keyboard[0][0].web_app.url
                assert inline_url == keyboard_url == base + '/'
                if external == 101:
                    # A keyboard WebView can lack signed initData. Follow its recovery hint.
                    signed_data, launch_data = launch_data, ''
                    await page.goto(keyboard_url)
                    await expect(page.locator('#status')).to_contain_text('/miniapp')
                    launch_data = signed_data
                async with page.expect_response(lambda response: response.url == base + '/api/v1/session') as login:
                    await page.goto(keyboard_url if external == 100 else inline_url)
                session = await login.value
                assert session.status == 200
                if external == 101:
                    tester_headers = {'Authorization': 'Bearer ' + (await session.json())['token']}
                await expect(page.locator('#catalogue')).to_be_visible()
                await expect(page.locator('#models')).to_contain_text('MA-01 Image')
                await page.get_by_role('button', name='Баланс').click()
                await expect(page.locator('#available')).to_have_text(str(credits))
                await expect(page.locator('#reserved')).to_have_text('0')
                await page.get_by_role('button', name='Мои работы').click()
                await expect(page.locator('#works > li')).to_have_count(1)
                await expect(page.locator('#works > li')).to_contain_text(model)
                async with page.expect_download() as download:
                    await page.get_by_role('button', name='Скачать').click()
                file = await download.value
                assert file.suggested_filename == 'darkflow.png'
                assert (await file.path()).read_bytes() == content
                await page.get_by_role('button', name='Настройки').click()
                await expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
                if external == 100:
                    await page.get_by_label('Светлая').check()
                    await expect(page.locator('#theme-status')).to_have_text('Тема сохранена.')
                    await expect(page.locator('html')).to_have_attribute('data-theme', 'light')
                if external == 100:
                    await page.get_by_role('button', name='Каталог').click()
                    await check_flux_confirmation(page, telegram.pool, owner, pending_jobs)
                else:
                    await check_job_card(page, telegram.pool, tester)
                    await compare_model_cards(page, telegram, owner, tester)
                await context.close()
        finally:
            await browser.close()

    foreign = await client.get(f'{base}/api/v1/works/image/{work_ids[0]}', headers=tester_headers)
    assert foreign.status == 404 and 'Content-Disposition' not in foreign.headers
    assert await foreign.text() == '404: Not Found'


async def check_flux_confirmation(page, pool, owner, pending_jobs):
    from playwright.async_api import expect

    async def counts():
        return tuple(await pool.fetchrow("""
            SELECT (SELECT count(*) FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id
                    WHERE q.user_id=$1),
                   (SELECT count(*) FROM ledger WHERE user_id=$1 AND kind='task_reserve')
        """, owner))

    prompt = page.get_by_label('Описание изображения')
    calculate = page.get_by_role('button', name='Рассчитать стоимость')
    confirm = page.get_by_role('button', name='Подтвердить за 10 токенов')
    await prompt.fill('Первоначальный эскиз')
    await calculate.click()
    await expect(confirm).to_be_visible()
    await prompt.fill('Маяк под снегом')
    await expect(confirm).to_have_count(0)
    await calculate.click()
    await expect(confirm).to_be_visible()
    assert await counts() == (0, 0) and not pending_jobs
    await confirm.dblclick()
    await expect(page.locator('.image-form [role=status]')).to_have_text('Задание принято.')
    assert await counts() == (1, 1) and len(pending_jobs) == 1
    assert await pool.fetchval("SELECT dr FROM ledger WHERE user_id=$1 AND kind='task_reserve'", owner) == 10

    posts = []
    def provider(request):
        assert request.method == 'POST' and request.url.path == '/v1/images/generations'
        posts.append(json.loads(request.content))
        return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(MOCK_IMAGE).decode()}]})

    client_class = httpx.AsyncClient
    with patch.object(httpx, 'AsyncClient', side_effect=lambda **kw: client_class(transport=httpx.MockTransport(provider), **kw)):
        await pending_jobs.pop()()
    assert [(post['model'], post['prompt']) for post in posts] == [('flux-schnell', 'Маяк под снегом')]
    assert await counts() == (1, 1)
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1 AND kind='task_capture'", owner) == 1


async def check_job_card(page, pool, tester):
    from playwright.async_api import expect

    await page.get_by_role('button', name='Каталог').click()
    await page.get_by_label('Описание изображения').fill('Ледяной маяк')
    await page.get_by_role('button', name='Рассчитать стоимость').click()
    await page.get_by_role('button', name='Подтвердить за 10 токенов').click()
    await expect(page.locator('.image-form [role=status]')).to_have_text('Задание принято.')
    job = str(await pool.fetchval("SELECT quote_id FROM http_image_commands WHERE user_id=$1", tester))
    await page.get_by_role('button', name='Мои работы').click()
    await page.get_by_role('button', name='Открыть задание ' + job, exact=True).click()
    cancel = page.get_by_role('button', name='Отменить', exact=True)
    await expect(page.locator('#job-id')).to_have_text(job)
    await expect(page.locator('#job-status')).to_have_text('Ожидает запуска')
    await expect(cancel).to_be_visible()
    await page.reload()
    await expect(page.locator('#job-id')).to_have_text(job)
    await expect(page.locator('#job-status')).to_have_text('Ожидает запуска')
    await cancel.click()
    await expect(page.locator('#job-status')).to_have_text('Отменено')
    await page.reload()
    await expect(page.locator('#job-id')).to_have_text(job)
    await expect(page.locator('#job-status')).to_have_text('Отменено')
    await expect(cancel).to_have_count(0)
    ledger = await pool.fetch('SELECT kind, dr FROM ledger WHERE user_id=$1 AND task_quote_id=$2::uuid ORDER BY kind',
                              tester, job)
    assert [tuple(row) for row in ledger] == [('task_release', -10), ('task_reserve', 10)]


async def compare_model_cards(page, telegram, owner, tester):
    from playwright.async_api import expect

    model = 'flux-schnell'
    key = ('clodex', model, 'images.generate')
    admin = TelegramApp(telegram.pool, replace(telegram.cfg, admin_password='fixture-password'), Bot())
    await admin.handle(event(2000, '/admin'))
    await admin.handle(event(2001, admin.cfg.admin_password))
    assert admin.has_admin_session(100)

    async def publish(n):
        schema = {'properties': {'n': {'type': 'integer', 'minimum': n, 'maximum': n}}, 'required': ['n']}
        version = await admin.models.stage_capabilities(owner, 100, *key, schema)
        await admin.models.publish_capabilities(owner, 100, *key, version)
        return str(version)

    def buttons():
        return {b.text: b.callback_data for row in telegram.bot.sent[-1][1].inline_keyboard for b in row}

    async def catalogue():
        await telegram.callback(tester, 101, 'slist:current:image:0')
        await page.reload()
        await expect(page.locator('#models')).to_contain_text('MA-01 Image')

    version = await publish(1)
    await page.get_by_role('button', name='Каталог').click()
    await catalogue()
    await telegram.callback(tester, 101, buttons()['FLUX Schnell'])
    label = 'Количество изображений: 1'
    assert label in telegram.bot.sent[-1][0]
    flux = page.locator('#models > li').filter(has_text='FLUX Schnell')
    await expect(flux).to_contain_text(label)
    launch, = [data for data in buttons().values() if data.startswith('srun:')]
    await telegram.callback(tester, 101, launch)
    prompt = 'Один маяк на берегу'
    await telegram.handle(event(2010, prompt, chat=101))
    telegram_price = telegram.bot.sent[-1][0]
    assert 'Оценка: 10 ' in telegram_price, telegram_price
    await flux.get_by_label('Описание изображения').fill(prompt)
    await flux.get_by_role('button', name='Рассчитать стоимость').click()
    await expect(flux.get_by_role('button', name='Подтвердить за 10 токенов')).to_be_visible()
    await expect(flux.locator('[role=status]')).to_have_text('Оценка: 10 токенов.')
    quotes = await telegram.pool.fetch(
        "SELECT request::text,price::text FROM task_price_quotes WHERE user_id=$1 AND request->>'prompt'=$2",
        tester, prompt)
    assert len(quotes) == 2
    for row in quotes:
        request = json.loads(row['request'])
        assert request['params'] == {'n': 1} and request['model_version']['version'] == version
        assert json.loads(row['price'])['total'] == '10'

    # This adapter produces one image. A published rule requiring two has no runnable choice.
    await publish(2)
    await catalogue()
    await telegram.callback(tester, 101, buttons()['FLUX Schnell'])
    assert not any(data.startswith('srun:') for data in buttons().values())
    await expect(flux.get_by_role('button', name='Рассчитать стоимость')).to_have_count(0)

    await admin.handle(event(2011, '/revoke ' + ' '.join(key)))
    await catalogue()
    assert 'FLUX Schnell' not in buttons()
    await expect(flux).to_have_count(0)
