"""MA-01 browser journey on the running OP-01 HTTPS fixture."""
import base64
import hashlib
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
                   availability='key_available', operations=['images.generate'], protocols=['image-generation'])]
    models.append(dict(provider='clodex', id='flux-schnell', title='FLUX Schnell', availability='key_available',
                       operations=['images.generate'], protocols=['image-generation']))
    models.append(dict(provider='clodex', id='clodex-video/veo-3.1', title='Veo 3.1', availability='key_available',
                       operations=['video'], protocols=['openai-video']))
    await telegram.pricing.set_tariff(owner, 100, 'clodex', 'flux-schnell', 'images.generate', {'n': 1},
                                      basis='request', unit='darkflow_token', amount='10', expires=None, evidence='fixture')
    models.append(dict(provider='clodex', id='eleven-v4', title='ElevenLabs v4', availability='key_available',
                       operations=['audio.speech']))
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
            await check_support_journey(browser, telegram, owner, base)
            for external, _, credits, model, content in profiles:
                context = await browser.new_context(
                    viewport={'width': 320 if external == 101 else 1280, 'height': 800},
                    reduced_motion='reduce')
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
                    await page.route('**/api/v1/catalogue', lambda route: route.abort('internetdisconnected'),
                                     times=1)
                async with page.expect_response(lambda response: response.url == base + '/api/v1/session') as login:
                    await page.goto(keyboard_url if external == 100 else inline_url)
                session = await login.value
                assert session.status == 200
                original_token = (await session.json())['token']
                session_token = original_token
                if external == 101:
                    tester_headers = {'Authorization': 'Bearer ' + session_token}
                    await expect(page.get_by_role('status').first).to_have_text(
                        'Нет связи с сервером. Проверьте подключение.')
                    await page.keyboard.press('Tab')
                    retry = page.get_by_role('button', name='Повторить загрузку')
                    await expect(retry).to_be_focused()
                    assert await retry.evaluate("el => getComputedStyle(el).outlineStyle !== 'none'")
                    await page.keyboard.press('Enter')
                await expect(page.locator('#catalogue')).to_be_visible()
                await expect(page.locator('#models')).to_contain_text('MA-01 Image')
                await page.get_by_label('Студия').select_option('video')
                await expect(page.get_by_text('MA-01 Image', exact=False)).to_be_hidden()
                await page.get_by_label('Студия').select_option('')
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                await page.get_by_role('button', name='Баланс').click()
                await expect(page.locator('#available')).to_have_text(str(credits))
                await expect(page.locator('#reserved')).to_have_text('0')
                await page.get_by_role('button', name='Мои работы').click()
                await expect(page.locator('#works > li')).to_have_count(1)
                await expect(page.locator('#works > li')).to_contain_text(model)
                await page.get_by_role('button', name='Просмотр', exact=True).click()
                preview = page.get_by_role('img', name='Результат генерации')
                await expect(preview).to_be_visible()
                await expect(preview).to_have_js_property('complete', True)
                assert await preview.evaluate('image => image.naturalWidth') > 0
                await page.get_by_role('button', name='Закрыть просмотр', exact=True).click()
                await expect(preview).to_have_count(0)
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
                    video_job = await check_veo_video(page, telegram, owner, pending_jobs)
                    speech_job = await check_speech(page, telegram, owner, pending_jobs)
                    music_job = await check_music(page, telegram, owner, client, base, session_token)
                    # A different signed Telegram launch must obtain its own session.
                    launch_data = signed(cfg.token, external, query_id='ma01-other-launch')
                    async with page.expect_response(lambda response: response.url == base + '/api/v1/session') as login:
                        await page.reload()
                    replacement = await login.value
                    assert replacement.status == 200
                    assert (await replacement.json())['token'] != original_token
                    await check_model_visibility(page, telegram, owner)
                else:
                    await expect(page.get_by_role('button', name='Выбрать Veo', include_hidden=True)).to_have_count(0)
                    denied = await client.post(base + '/api/v1/quotes', headers=tester_headers,
                                               json={'model': 'clodex-video/veo-3.1', 'prompt': 'fixture'})
                    assert denied.status == 403
                    assert (await client.get(base + '/api/v1/works/video/' + video_job, headers=tester_headers)).status == 404
                    assert (await client.get(base + '/api/v1/jobs/' + video_job, headers=tester_headers)).status == 404
                    assert (await client.get(base + '/api/v1/works/audio/' + speech_job, headers=tester_headers)).status == 404
                    assert (await client.get(base + '/api/v1/works/music/' + music_job, headers=tester_headers)).status == 404
                    await check_job_card(page, telegram.pool, tester)
                    await compare_model_cards(page, telegram, owner, tester)
                await context.close()
            await check_consent_journey(browser, telegram, base, client)
        finally:
            await browser.close()

    foreign = await client.get(f'{base}/api/v1/works/image/{work_ids[0]}', headers=tester_headers)
    assert foreign.status == 404 and 'Content-Disposition' not in foreign.headers
    assert await foreign.text() == '404: Not Found'


async def check_support_journey(browser, telegram, operator, base):
    from playwright.async_api import expect

    async def launch(context, subject):
        launch_data = signed(telegram.cfg.token, subject, query_id='sl02-browser')

        async def sdk(route):
            await route.fulfill(content_type='application/javascript', body=
                'window.Telegram={WebApp:{ready(){},initData:' + json.dumps(launch_data) + '}};')

        await context.route('https://telegram.org/js/telegram-web-app.js', sdk)
        page = await context.new_page()
        await page.goto(base)
        await expect(page.locator('#catalogue')).to_be_visible()
        return page

    owner_context = await browser.new_context(viewport={'width': 320, 'height': 800})
    operator_context = await browser.new_context()
    owner_page = await launch(owner_context, 101)
    operator_page = await launch(operator_context, 100)
    try:
        await owner_page.get_by_role('button', name='Поддержка', exact=True).click()
        for body in ('Не получается скачать работу', 'Вопрос о настройках'):
            await owner_page.get_by_label('Текст обращения').fill(body)
            await owner_page.get_by_role('button', name='Отправить', exact=True).click()
            await expect(owner_page.get_by_label('Текст обращения')).to_have_value('')
        await expect(owner_page.locator('#owner-support-list button')).to_have_count(2)
        assert await owner_page.evaluate('document.documentElement.scrollWidth <= innerWidth')

        await operator_page.get_by_role('button', name='Поддержка', exact=True).click()
        await expect(operator_page.locator('#support-status')).to_have_text('Обращений пока нет.')
        await telegram.pool.execute("""INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,'OWNER_ADMIN','synthetic browser grant')""", operator)
        await operator_page.get_by_role('button', name='Администрирование', exact=True).click()
        await expect(operator_page.locator('#admin-status')).to_have_text('Обзор за 7 дней · OWNER_ADMIN')
        await expect(operator_page.get_by_text('Пользователи: 2', exact=True)).to_be_visible()
        await expect(operator_page.get_by_text('Текущая доступность провайдеров: не проверена')).to_be_visible()
        await expect(operator_page.get_by_text('Случаев на сверке за период: 0.')).to_be_visible()
        await operator_page.get_by_text('Платежи', exact=True).click()
        await expect(operator_page.locator('details[open]')).to_contain_text('Нет данных за период.')

        select = operator_page.get_by_label('Обращение', exact=True)
        await expect(select.locator('option')).to_have_count(2)
        await expect(operator_page.get_by_text('Пользователь: Вопрос о настройках', exact=True)).to_be_visible()
        await select.select_option(index=1)
        await expect(operator_page.get_by_text('Пользователь: Не получается скачать работу', exact=True)).to_be_visible()
        await operator_page.get_by_label('Ответ оператора').fill('Уточните название работы.')
        await operator_page.get_by_role('button', name='Сохранить ответ').click()
        await expect(operator_page.get_by_text('Оператор: Уточните название работы.', exact=True)).to_be_visible()
        await expect(select.locator('option:checked')).to_contain_text('Есть ответ')

        await owner_page.get_by_role('button', name='Обновить обращения').click()
        await owner_page.get_by_role('button', name='Есть ответ').click()
        history = owner_page.get_by_role('list', name='Переписка')
        await expect(history).to_contain_text('Вы: Не получается скачать работу')
        await expect(history).to_contain_text('Поддержка: Уточните название работы.')

        await telegram.pool.execute("""INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,NULL,'synthetic browser revocation')""", operator)
        await operator_page.get_by_label('Ответ оператора').fill('Этот ответ должен быть отклонён.')
        async with operator_page.expect_response(lambda r: r.url.endswith('/api/v1/admin/support/reply')) as denied:
            await operator_page.get_by_role('button', name='Сохранить ответ').click()
        assert (await denied.value).status == 403
        await expect(operator_page.get_by_role('button', name='Сохранить ответ')).to_have_count(0)
        assert await telegram.pool.fetchval('SELECT count(*) FROM support_operator_replies') == 1
        await operator_page.get_by_role('button', name='Баланс', exact=True).click()
        await expect(operator_page.locator('#available')).to_have_text('1200')
        print('MINIAPP_SL02=pass; POSTGRES_RBAC=pass; OWNER_ISOLATION=pass; ADMIN_OPERATIONS=pass')
    finally:
        await operator_context.close()
        await owner_context.close()


async def check_consent_journey(browser, telegram, base, client):
    from playwright.async_api import expect

    subject = 103
    await telegram.handle(event(6000, '/start', chat=subject))
    user = await telegram.pool.fetchval(
        "SELECT user_id FROM identities WHERE platform='telegram' AND external_id=$1", subject
    )
    assert user is not None
    await telegram.handle(event(6001, '/miniapp', chat=subject))
    launch_url = telegram.bot.sent[-1][1].inline_keyboard[0][0].web_app.url
    assert launch_url == base + '/'
    session_url = base + '/api/v1/session'
    launch_data = signed(telegram.cfg.token, subject, query_id='sl03-consent')
    docs = telegram.svc.get_consent_documents()
    stale = await client.post(session_url, json={'initData': launch_data, 'terms_version': 'previous'})
    assert stale.status == 428 and await stale.json() == docs
    async with telegram.pool.acquire() as conn:
        assert not await telegram.svc.has_current_consent(conn, user)

    context = await browser.new_context(viewport={'width': 320, 'height': 800})
    try:
        async def sdk(route):
            await route.fulfill(content_type='application/javascript', body=
                'window.Telegram={WebApp:{ready(){},initData:' + json.dumps(launch_data) + '}};')

        await context.route('https://telegram.org/js/telegram-web-app.js', sdk)
        page = await context.new_page()
        async with page.expect_response(session_url) as pending:
            await page.goto(launch_url)
        assert (await pending.value).status == 428
        await expect(page.get_by_role('heading', name='Условия доступа')).to_be_visible()
        await expect(page.locator('nav')).to_be_hidden()
        await page.get_by_text('Условия использования', exact=True).click()
        await expect(page.locator('#consent details[open] pre')).to_have_text(docs['terms'].strip())
        await page.get_by_text('Обработка данных', exact=True).click()
        await expect(page.locator('#consent details[open] pre').last).to_have_text(docs['privacy'].strip())
        async with page.expect_response(session_url) as accepted:
            await page.get_by_role('button', name='Принять условия и продолжить').click()
        assert (await accepted.value).status == 200
        await expect(page.get_by_role('heading', name='Каталог')).to_be_visible()
        await page.get_by_role('button', name='Профиль', exact=True).click()
        await expect(page.locator('#profile-status')).to_have_text('Telegram ID: 103 · Условия приняты')
        await expect(page.locator('#profile-documents')).to_contain_text('Версия документов ' + docs['version'])
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')

        launch_data = signed(telegram.cfg.token, subject, query_id='sl03-returning')
        async with page.expect_response(session_url) as reopened:
            await page.reload()
        assert (await reopened.value).status == 200
        await expect(page.get_by_role('button', name='Принять условия и продолжить')).to_be_hidden()
        async with telegram.pool.acquire() as conn:
            await telegram.svc.authorize(conn, user)
        await telegram.handle(event(6002, '/start', chat=subject))
        assert await telegram.svc.welcome_message(subject) is not None
        print('MINIAPP_SL03=pass; SHARED_CONSENT=pass; LEGAL_VERSION=pass; PROFILE=pass')
    finally:
        await context.close()


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

    # An unknown provider outcome must remain visible without offering cancellation.
    await page.get_by_role('button', name='Каталог').click()
    await page.get_by_label('Описание изображения').fill('Неопределённый результат')
    await page.get_by_role('button', name='Рассчитать стоимость').click()
    await page.get_by_role('button', name='Подтвердить за 10 токенов').click()
    await expect(page.locator('.image-form [role=status]')).to_have_text('Задание принято.')
    uncertain = str(await pool.fetchval("""SELECT quote_id FROM http_image_commands
        WHERE user_id=$1 AND quote_id<>$2::uuid""", tester, job))
    await pool.execute("UPDATE task_dispatch SET state='uncertain' WHERE quote_id=$1::uuid", uncertain)
    await page.get_by_role('button', name='Мои работы').click()
    await page.get_by_role('button', name='Открыть задание ' + uncertain, exact=True).click()
    await expect(page.locator('#job-status')).to_have_text('Результат пока неизвестен')
    await expect(cancel).to_have_count(0)
    await page.reload()
    await expect(page.locator('#job-status')).to_have_text('Результат пока неизвестен')
    await expect(cancel).to_have_count(0)
    assert await pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1::uuid AND kind='task_release'", uncertain) == 0


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


async def check_veo_video(page, telegram, owner, pending_jobs):
    from playwright.async_api import expect
    from elevenbot.video import MODES

    model = 'clodex-video/veo-3.1'
    prompt = 'Маяк на рассвете'
    mp4 = Path(__file__).resolve().parents[2].joinpath('src/elevenbot/darkflow-energy-strip-1200x80-2x.mp4').read_bytes()
    calls = []
    def provider(request):
        calls.append((request.method, request.url.path))
        if request.method == 'POST':
            assert json.loads(request.content) == dict(model=model, prompt=prompt, duration=4,
                                                      resolution='720p', aspect_ratio='16:9')
            if request.url.path.endswith('/estimate'):
                return httpx.Response(200, json={'success': True, 'data': {'model': model, 'cost_usd': '0.45'}})
            assert request.url.path == '/v1/videos'
            return httpx.Response(200, json={'id': 'veo-fixture-' + str(calls.count(('POST', '/v1/videos')))})
        if request.url.path.endswith('/content'):
            return httpx.Response(200, content=mp4, headers={'Content-Type': 'video/mp4'})
        assert request.url.path in ('/v1/videos/veo-fixture-1', '/v1/videos/veo-fixture-2')
        return httpx.Response(200, json={'status': 'done'})

    telegram.video.api.transport = httpx.MockTransport(provider)
    telegram.bot.send_video = AsyncMock(return_value=SimpleNamespace(message_id=4100))
    await telegram.pricing.set_rate(owner, 100, 'USD', '1000')
    await page.get_by_role('button', name='Выбрать Veo 3.1 · Обычный').click()
    card = page.locator('#models > li').filter(has_text='Veo 3.1')
    await expect(card).to_contain_text('4 с · 720p · 16:9')
    await card.get_by_label('Описание видео').fill(prompt)
    await card.get_by_role('button', name='Рассчитать стоимость').click()
    confirm = card.get_by_role('button', name='Подтвердить за 450 токенов')
    await expect(confirm).to_be_visible()
    assert calls == [('POST', '/v1/videos/estimate')]
    assert not await telegram.pool.fetchval("SELECT count(*) FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id WHERE q.user_id=$1 AND q.operation='video'", owner)
    await confirm.dblclick()
    await expect(page.locator('#job-status')).to_have_text('Ожидает запуска')
    job = await page.locator('#job-id').inner_text()
    assert len(pending_jobs) == 1
    assert await telegram.pool.fetchval("SELECT count(*) FROM task_dispatch WHERE quote_id=$1::uuid", job) == 1
    assert await telegram.pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1::uuid AND kind='task_reserve'", job) == 1
    await pending_jobs.pop()()
    await page.get_by_role('button', name='Обновить статус').click()
    await expect(page.locator('#job-status')).to_have_text('Передано исполнителю')
    assert await telegram.video.poll_one(telegram.bot)
    await page.get_by_role('button', name='Обновить статус').click()
    await expect(page.locator('#job-status')).to_have_text('Завершено')
    await page.get_by_role('button', name='К списку').click()
    work = page.locator('#works > li').filter(has_text='Видео')
    async with page.expect_download() as downloaded:
        await work.get_by_role('button', name='Скачать').click()
    file = await downloaded.value
    assert file.suggested_filename == 'darkflow.mp4' and (await file.path()).read_bytes() == mp4

    await telegram.handle(event(4000, '📁 Мои работы'))
    keys = [b.callback_data for row in telegram.bot.sent[-1][1].inline_keyboard for b in row]
    assert 'video:' + job in keys
    telegram.bot.send_video.reset_mock()
    await telegram.handle(event(4001, callback='video:' + job))
    telegram.bot.send_video.assert_awaited_once()
    chat, upload = telegram.bot.send_video.await_args.args
    assert chat == 100 and upload.data == mp4
    assert calls.count(('POST', '/v1/videos')) == 1
    assert calls.count(('GET', '/v1/videos/veo-fixture-1/content')) == 1
    # The bot's maintenance loop settles terminal work independently of polling.
    from elevenbot.task_wallet import settle_task_tokens
    await settle_task_tokens(telegram.pool)
    await settle_task_tokens(telegram.pool)
    assert await telegram.pool.fetchval("SELECT count(*) FROM ledger WHERE task_quote_id=$1::uuid AND kind='task_capture'", job) == 1

    def button(label):
        return next(item.callback_data for row in telegram.bot.sent[-1][1].inline_keyboard
                    for item in row if item.text == label)

    await telegram.handle(event(4011, callback='slist:current:video:0'))
    await telegram.handle(event(4012, callback=button('Veo 3.1')))
    await telegram.handle(event(4013, callback=button(MODES['standard'][2])))
    await telegram.handle(event(4014, prompt))
    confirm_telegram = button('Генерировать')
    assert '450' in telegram.bot.sent[-1][0]
    await telegram.handle(event(4015, callback=confirm_telegram))
    assert await telegram.video.poll_one(telegram.bot)
    await settle_task_tokens(telegram.pool)
    await page.get_by_role('button', name='Мои работы').click()
    telegram_work = page.locator('#works > li').filter(has_text='Видео')
    await expect(telegram_work).to_have_count(2)
    async with page.expect_download() as downloaded:
        await telegram_work.first.get_by_role('button', name='Скачать').click()
    assert (await (await downloaded.value).path()).read_bytes() == mp4
    assert calls.count(('POST', '/v1/videos')) == 2
    assert calls.count(('GET', '/v1/videos/veo-fixture-2/content')) == 1
    assert await telegram.pool.fetchval("""
        SELECT count(*) FROM ledger JOIN task_price_quotes q ON q.id=task_quote_id
        WHERE q.user_id=$1 AND q.operation='video' AND ledger.kind='task_capture'
        """, owner) == 2
    return job


async def check_speech(page, telegram, owner, pending_jobs):
    from playwright.async_api import expect

    voice = 'fixture-voice'
    prompt = 'Я😀!'
    mp3 = Path(__file__).resolve().parents[2].joinpath('assets/demo.mp3').read_bytes()
    await telegram.pricing.set_tariff(owner, 100, 'clodex', 'eleven_v4', 'audio.speech', {'voice': voice},
                                      basis='utf16', unit='darkflow_token', amount='20', expires=None, evidence='fixture')
    def buttons():
        return {b.text: b.callback_data for row in telegram.bot.sent[-1][1].inline_keyboard for b in row}

    async def telegram_quote(update_id):
        await telegram.callback(owner, 100, 'slist:current:speech:0')
        await telegram.callback(owner, 100, buttons()['ElevenLabs v4'])
        launch, = [data for data in buttons().values() if data.startswith('srun:')]
        with patch('elevenbot.providers.voice_candidates', AsyncMock(return_value={'candidates': [
                {'id': voice, 'name': 'Голос стенда'}]})):
            await telegram.callback(owner, 100, launch)
        await telegram.callback(owner, 100, buttons()['Голос стенда'])
        await telegram.handle(event(update_id, prompt))
        assert 'Оценка: 80 ' in telegram.bot.sent[-1][0], telegram.bot.sent[-1][0]
        return buttons()['Генерировать']

    await telegram_quote(4200)

    await page.get_by_role('button', name='Каталог').click()
    await page.reload()
    card = page.locator('#models > li').filter(has_text='ElevenLabs v4')
    await card.get_by_role('button', name='Выбрать голос').click()
    await card.get_by_label('Голос').select_option(label='Голос стенда')
    await card.get_by_label('Текст для озвучки').fill(prompt)
    await card.get_by_role('button', name='Рассчитать стоимость').click()
    confirm = card.get_by_role('button', name='Подтвердить за 80 токенов')
    await expect(confirm).to_be_visible()
    assert not await telegram.pool.fetchval("SELECT count(*) FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id WHERE q.user_id=$1 AND q.operation='audio.speech'", owner)
    await confirm.dblclick()
    await expect(page.locator('#job-status')).to_have_text('Ожидает запуска')
    job = await page.locator('#job-id').inner_text()
    assert await telegram.pool.fetchval("SELECT count(*) FROM task_dispatch WHERE quote_id=$1::uuid", job) == 1
    posts = []
    def provider(request):
        assert request.method == 'POST' and request.url.path == '/v1/audio/speech'
        posts.append(json.loads(request.content))
        return httpx.Response(200, content=mp3, headers={'Content-Type': 'audio/mpeg'})

    client_class = httpx.AsyncClient
    assert len(pending_jobs) == 1
    with patch.object(httpx, 'AsyncClient', side_effect=lambda **kw: client_class(transport=httpx.MockTransport(provider), **kw)):
        await pending_jobs.pop()()
    assert posts == [dict(model='eleven_v4', voice=voice, input=prompt)]
    await page.get_by_role('button', name='Обновить статус').click()
    await expect(page.locator('#job-status')).to_have_text('Завершено')
    ledger = await telegram.pool.fetch("""
        SELECT l.kind,l.da,l.dr FROM ledger l JOIN task_price_quotes q ON q.id=l.task_quote_id
        WHERE q.user_id=$1 AND q.operation='audio.speech' ORDER BY l.kind
    """, owner)
    assert [tuple(row) for row in ledger] == [('task_capture', 0, -80), ('task_reserve', -80, 80)]
    await page.get_by_role('button', name='К списку').click()
    work = page.locator('#works > li').filter(has_text='Аудио')
    async with page.expect_download() as downloaded:
        await work.get_by_role('button', name='Скачать').click()
    file = await downloaded.value
    assert file.suggested_filename == 'darkflow.mp3' and (await file.path()).read_bytes() == mp3
    await telegram.handle(event(4201, '📁 Мои работы'))
    callback = 'get:' + job
    assert callback in buttons().values()
    telegram.bot.audio.clear()
    await telegram.handle(event(4202, callback=callback))
    (args, _), = telegram.bot.audio
    assert args[0] == 100 and args[1].data == mp3
    telegram_confirm = await telegram_quote(4203)
    with patch.object(httpx, 'AsyncClient', side_effect=lambda **kw: client_class(transport=httpx.MockTransport(provider), **kw)):
        await telegram.handle(event(4204, callback=telegram_confirm))
    assert posts == [dict(model='eleven_v4', voice=voice, input=prompt)] * 2
    await page.get_by_role('button', name='Мои работы').click()
    await expect(work).to_have_count(2)
    async with page.expect_download() as downloaded:
        await work.first.get_by_role('button', name='Скачать').click()
    assert (await (await downloaded.value).path()).read_bytes() == mp3
    assert await telegram.pool.fetchval("""
        SELECT count(*) FROM ledger JOIN task_price_quotes q ON q.id=task_quote_id
        WHERE q.user_id=$1 AND q.operation='audio.speech' AND ledger.kind='task_capture'
        """, owner) == 2
    return job


async def check_music(page, view, owner, client, base, token):
    from playwright.async_api import expect
    from elevenbot.clodex_music import AUDIOS, MODEL

    # A different Telegram process owns the Admin Edition session and worker.
    bot = TelegramApp(view.pool, view.cfg, view.bot)
    prompt = 'Ночная прогулка, спокойное фортепиано'
    mp3 = Path(__file__).resolve().parents[2].joinpath('assets/demo.mp3').read_bytes()
    creates = []
    def provider(req):
        if req.url.path == AUDIOS + '/estimate':
            return httpx.Response(200, json={'success': True, 'data': {'model': MODEL, 'cost_usd': '0.1'}})
        if req.url.path == AUDIOS:
            assert req.method == 'POST'
            creates.append(json.loads(req.content))
            return httpx.Response(202, json={'id': 'fixture-track'})
        if req.url.path == AUDIOS + '/fixture-track':
            return httpx.Response(200, json={'status': 'done'})
        assert req.url.path == AUDIOS + '/fixture-track/content'
        return httpx.Response(200, content=mp3, headers={'content-type': 'audio/mpeg'})

    bot.music.api.transport = view.music.api.transport = httpx.MockTransport(provider)
    headers = {'Authorization': 'Bearer ' + token}
    async def counts():
        return tuple(await view.pool.fetchrow("""
            SELECT (SELECT count(*) FROM clodex_music_jobs WHERE user_id=$1),
                   (SELECT count(*) FROM clodex_music_ledger WHERE user_id=$1 AND kind='capture')
        """, owner))

    async with bot.music.host_miniapp_session():
        assert (await client.post(base + '/api/v1/quotes', headers=headers,
                                  json={'model': MODEL, 'prompt': prompt})).status == 403
        await bot.handle(event(4300, '/admin'))
        await bot.handle(event(4301, bot.cfg.admin_password))
        assert bot.music_access(100) and not view.music_access(100)
        await page.get_by_role('button', name='Каталог').click()
        await page.reload()
        card = page.locator('#models > li').filter(has_text='Leonardo Music')
        for limit in ('Одна попытка', 'Один MP3', 'До 5000 символов', 'Хранение 7 дней', 'Лицензия не указана'):
            await expect(card).to_contain_text(limit)
        await card.get_by_role('button', name='Выбрать Leonardo Music').click()
        await card.get_by_label('Описание трека').fill(prompt)
        async with page.expect_response(lambda r: r.url.endswith('/api/v1/quotes')) as quoted:
            await card.get_by_role('button', name='Рассчитать стоимость').click()
        quote = await (await quoted.value).json()
        confirm = card.get_by_role('button', name='Подтвердить за 100 токенов')
        await expect(confirm).to_be_visible()
        # The operator funds the isolated pilot wallet using the existing MU-01 grant.
        assert await bot.music.grant(owner, 100, quote['quote_id']) == 100
        assert await counts() == (0, 0) and creates == []
        await confirm.click()
        work = page.locator('#works > li').filter(has_text=MODEL)
        await expect(work).to_contain_text('В очереди')
        for _ in range(3):
            assert await bot.music.tick(bot.bot)
        assert creates == [dict(model=MODEL, prompt=prompt, n=1)]
        await page.get_by_role('button', name='Мои работы').click()
        await expect(work).to_contain_text('Готово')
        job = quote['quote_id']
        assert await counts() == (1, 1)
        replay = await client.post(base + '/api/v1/jobs', json={'quote_id': job},
                                   headers={**headers, 'Idempotency-Key': job})
        assert replay.status == 200 and (await replay.json())['id'] == job
        for attempt in range(2):
            async with page.expect_download() as downloaded:
                await work.get_by_role('button', name='Скачать').click()
            file = await downloaded.value
            assert (await file.path()).read_bytes() == mp3
            await bot.handle(event(4302 + 2*attempt, '📁 Мои работы'))
            keys = [b.callback_data for row in bot.bot.sent[-1][1].inline_keyboard for b in row]
            assert 'musicwork:' + job in keys
            bot.bot.audio.clear()
            await bot.handle(event(4303 + 2*attempt, callback='musicwork:' + job))
            (args, _), = bot.bot.audio
            assert args[0] == 100 and args[1].data == mp3
        assert await counts() == (1, 1) and len(creates) == 1
        assert tuple(await bot.music.balance(owner)) == (0, 0)
        assert not await view.pool.fetchval('SELECT count(*) FROM ledger WHERE task_quote_id=$1::uuid', job)

        # Expire both the process-local session and its server-side proof without logout.
        before_job = await view.pool.fetchrow('SELECT * FROM clodex_music_jobs WHERE id=$1::uuid', job)
        before_ledger = await view.pool.fetch('SELECT * FROM clodex_music_ledger ORDER BY user_id,kind,provider')
        before_wallet = await view.pool.fetch('SELECT * FROM ledger ORDER BY id')
        before_quotes = await view.pool.fetch('SELECT * FROM task_price_quotes ORDER BY id')
        assert (await client.get(base + '/api/v1/works/music/' + job, headers=headers)).status == 200
        visible = await (await client.get(base + '/api/v1/works', headers=headers)).json()
        assert any(item['id'] == job for item in visible['works'])
        await view.pool.execute("UPDATE miniapp_music_sessions SET expires_at=clock_timestamp()-interval '1 second' WHERE chat_id=100")
        from elevenbot import admin_access
        bot.admin_access.sessions[100] = (admin_access.monotonic() - 1, bot.admin_access.sessions[100][1])
        assert not await view.music.miniapp_access(view.pool, 100)
        assert (await client.get(base + '/api/v1/works/music/' + job, headers=headers)).status == 404
        assert (await client.post(base + '/api/v1/quotes', headers=headers,
                                  json={'model': MODEL, 'prompt': prompt})).status == 403
        catalogue_response = await client.get(base + '/api/v1/catalogue', headers=headers)
        history_response = await client.get(base + '/api/v1/works', headers=headers)
        assert catalogue_response.status == history_response.status == 200
        catalogue, history = await catalogue_response.json(), await history_response.json()
        assert not any(item['id'] == MODEL for item in catalogue['models'])
        assert not any(item['id'] == job for item in history['works'])
        assert await view.pool.fetchrow('SELECT * FROM clodex_music_jobs WHERE id=$1::uuid', job) == before_job
        assert await view.pool.fetch('SELECT * FROM clodex_music_ledger ORDER BY user_id,kind,provider') == before_ledger
        assert await view.pool.fetch('SELECT * FROM ledger ORDER BY id') == before_wallet
        assert await view.pool.fetch('SELECT * FROM task_price_quotes ORDER BY id') == before_quotes
        assert len(creates) == 1
        await bot.handle(event(4307, '/admin'))
        await bot.handle(event(4308, bot.cfg.admin_password))
        restored = await client.get(base + '/api/v1/works/music/' + job, headers=headers)
        assert restored.status == 200 and await restored.read() == mp3
        assert await view.music.miniapp_access(view.pool, 100)
        visible_again = await (await client.get(base + '/api/v1/works', headers=headers)).json()
        assert any(item['id'] == job for item in visible_again['works'])
        await bot.handle(event(4309, '/admin_logout'))
        assert (await client.get(base + '/api/v1/works/music/' + job, headers=headers)).status == 404
        return job



async def check_model_visibility(page, telegram, owner):
    from playwright.async_api import expect

    await telegram.pool.execute('''
        INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
        VALUES($1,$1,'SETTINGS_OPERATOR','OP-01 visibility grant')
    ''', owner)
    await page.get_by_role('button', name='Администрирование').click()
    models = page.get_by_label('Модель', exact=True)
    await expect(models.locator('option').filter(has_text='Image · clodex')).to_contain_text('Видима')
    await models.select_option(label='Image · clodex · images.generate · Видима')
    await page.get_by_role('button', name='Предпросмотр скрытия').click()
    await expect(page.get_by_text('Image · Видима → Скрыта')).to_be_visible()
    await page.get_by_role('button', name='Подтвердить видимость').click()
    await expect(models.locator('option').filter(has_text='Image · clodex')).to_contain_text('Скрыта')
    # The same PostgreSQL value drives both catalogues, including a live refresh
    # of the Mini App list after confirmation.
    snapshot = telegram.catalogue_snapshot()
    indices = await telegram.store_models(snapshot, 'image', None)
    assert 'fixture/image' not in {snapshot['models'][i]['id'] for i in indices}
    await page.get_by_role('button', name='Каталог', exact=True).click()
    await expect(page.locator('#models')).not_to_contain_text('MA-01 Image')
    await page.get_by_role('button', name='Администрирование').click()
    await expect(models.locator('option').filter(has_text='Image · clodex')).to_contain_text('Скрыта')
    await models.select_option(label='Image · clodex · images.generate · Скрыта')
    await page.get_by_role('button', name='Предпросмотр отката').click()
    await expect(page.get_by_text('Image · Скрыта → Видима')).to_be_visible()
    await page.get_by_role('button', name='Подтвердить видимость').click()
    await expect(models.locator('option').filter(has_text='Image · clodex')).to_contain_text('Видима')
    await page.get_by_role('button', name='Каталог', exact=True).click()
    await expect(page.locator('#models')).to_contain_text('MA-01 Image')

    await telegram.pool.execute('''
        INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
        VALUES($1,$1,NULL,'OP-01 visibility revoke')
    ''', owner)
    await page.get_by_role('button', name='Администрирование').click()
    await expect(models).to_have_count(0)
    await page.get_by_role('button', name='Каталог', exact=True).click()
    await expect(page.locator('#models')).to_contain_text('MA-01 Image')
