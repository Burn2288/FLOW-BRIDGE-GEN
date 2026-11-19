"""MA-01 browser journey on the running OP-01 HTTPS fixture."""
import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from elevenbot.aggregate import make_snapshot
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from miniapp.tests.test_miniapp import signed
from test_admin_access import event


async def check_miniapp_journey(telegram, owner, tester, base, cert, client):
    from playwright.async_api import async_playwright, expect

    cfg = telegram.cfg
    models = [dict(provider='clodex', id='fixture/image', title='MA-01 Image',
                   availability='key_available', operations=['images.generate'])]
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
                await context.close()
        finally:
            await browser.close()

    foreign = await client.get(f'{base}/api/v1/works/image/{work_ids[0]}', headers=tester_headers)
    assert foreign.status == 404 and 'Content-Disposition' not in foreign.headers
    assert await foreign.text() == '404: Not Found'
