"""Record the Mini App continuation of a funded DEV commercial fixture."""

import argparse
import asyncio
import hashlib
import json
import shutil
from pathlib import Path
from uuid import UUID

from playwright.async_api import async_playwright, expect

from verification.studio_matrix import open_client


async def paid_work(page, artifacts):
    await page.get_by_role('button', name='Баланс', exact=True).click()
    await expect(page.locator('#stars-history')).to_contain_text('Оплачен')
    await page.screenshot(path=artifacts / 'balance.png', full_page=True)

    await page.get_by_role('button', name='Мои работы', exact=True).click()
    work = page.locator('#works > li').filter(has_text='P06 finance').first
    await expect(work.get_by_role('button', name='Скачать')).to_be_enabled()
    async with page.expect_download() as download:
        await work.get_by_role('button', name='Скачать').click()
    path = await (await download.value).path()
    content = path.read_bytes()
    assert content, 'Empty fixture media'
    await page.screenshot(path=artifacts / 'library.png', full_page=True)
    return hashlib.sha256(content).hexdigest()


async def referrals(page, artifacts):
    await page.get_by_role('button', name='Приглашения', exact=True).click()
    await expect(page.locator('#copy-referral')).to_be_enabled()
    await page.locator('#load-referral-finances').click()
    await expect(page.locator('#referral-finances-history')).to_contain_text('Начисление')
    await page.screenshot(path=artifacts / 'referrals.png', full_page=True)


async def support(owner, operator, base, artifacts):
    text = 'Проверка заказа из демонстрационного сценария.'
    reply = 'Демонстрационная работа доступна в библиотеке.'
    await owner.get_by_role('button', name='Поддержка', exact=True).click()
    await owner.get_by_label('Текст обращения').fill(text)
    async with owner.expect_response(
        lambda response: response.url == base + '/api/v1/support' and response.request.method == 'POST'
    ) as created:
        await owner.locator('#owner-support-create').click()
    response = await created.value
    assert response.ok, f'Fixture support creation failed with HTTP {response.status}'
    ticket = str(UUID((await response.json())['id']))

    await operator.get_by_role('button', name='Администрирование', exact=True).click()
    await operator.get_by_label('Обращение', exact=True).select_option(ticket)
    await expect(operator.locator('.operator-support')).to_contain_text(text)
    await operator.get_by_label('Ответ оператора').fill(reply)
    await operator.get_by_role('button', name='Сохранить ответ').click()
    await expect(operator.locator('.operator-support')).to_contain_text('Ответ сохранён.')
    await operator.screenshot(path=artifacts / 'administration.png', full_page=True)

    async with owner.expect_response(base + '/api/v1/support'):
        await owner.locator('#owner-support-refresh').click()
    newest = owner.locator('#owner-support-list button').first
    await expect(newest).to_contain_text('Есть ответ')
    async with owner.expect_response(base + '/api/v1/support?ticket_id=' + ticket):
        await newest.click()
    await expect(owner.locator('#owner-support-history')).to_contain_text(reply)
    await owner.screenshot(path=artifacts / 'support.png', full_page=True)


async def run(args):
    chromium = shutil.which('chromium') or shutil.which('google-chrome')
    if not chromium:
        raise SystemExit('Chromium or Google Chrome is required.')
    args.artifacts.mkdir(parents=True, exist_ok=True)
    base = f'http://127.0.0.1:{args.miniapp_port}'
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path=chromium)
        try:
            owner_context = await browser.new_context(viewport={'width': 390, 'height': 844})
            owner = await open_client(owner_context, base, args.actor)
            await expect(owner.get_by_label('Студия')).to_be_enabled()
            await expect(owner.locator('#models > li').first).to_be_visible()
            await owner.screenshot(path=args.artifacts / 'catalogue.png', full_page=True)
            digest = await paid_work(owner, args.artifacts)
            await referrals(owner, args.artifacts)

            operator_context = await browser.new_context(viewport={'width': 1280, 'height': 900})
            operator = await open_client(operator_context, base, args.operator, accept_terms=True)
            await support(owner, operator, base, args.artifacts)
        finally:
            await browser.close()

    evidence = {'synthetic_payment_history': 'paid', 'download_sha256': digest, 'support': 'answered'}
    (args.artifacts / 'commercial-demo.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--miniapp-port', type=int, default=8091)
    parser.add_argument('--actor', type=int, default=104, help='P06 invite owner with payment and stored work')
    parser.add_argument('--operator', type=int, default=100, help='DEV operator with support.operate')
    parser.add_argument('--artifacts', type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
