"""Chromium coverage of the published Mini App UI with synthetic HTTP responses."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, expect


async def test_referral_history_is_paginated_exact_and_session_scoped():
    root = Path(__file__).resolve().parents[2] / 'miniapp/frontend'
    principal = 'first'
    fail_once = True
    finance_calls = []

    async def respond(route):
        nonlocal fail_once
        url = urlsplit(route.request.url)
        if url.hostname == 'telegram.org':
            return await route.fulfill(content_type='application/javascript', body=(
                'window.Telegram={WebApp:{initData:' + json.dumps(principal) + ',ready(){}}};'
            ))
        if url.path == '/':
            return await route.fulfill(content_type='text/html', body=(root / 'index.html').read_text(encoding='utf-8'))
        if url.path == '/assets/app.js':
            return await route.fulfill(content_type='application/javascript', body=(root / 'app.js').read_text(encoding='utf-8'))
        if url.path == '/assets/style.css':
            return await route.fulfill(content_type='text/css', body=(root / 'style.css').read_text(encoding='utf-8'))
        if url.path == '/api/v1/session':
            assert route.request.post_data_json['initData'] == principal
            return await route.fulfill(json={'token': principal})
        if url.path == '/api/v1/referral':
            assert route.request.headers.get('authorization') == 'Bearer ' + principal
            return await route.fulfill(json={'code': 'AAAAAAAAAAAAAAAA' if principal == 'first' else 'BBBBBBBBBBBBBBBB', 'has_referrer': False})
        if url.path == '/api/v1/referral/finances':
            assert route.request.headers.get('authorization') == 'Bearer ' + principal
            page = int(url.query.split('=')[1])
            finance_calls.append((principal,page))
            if fail_once:
                fail_once = False
                return await route.fulfill(status=503, json={'error':'temporary'})
            first = principal == 'first'
            return await route.fulfill(json={
                'page': page, 'has_more': first and page == 0, 'invitee_count': int(first),
                'available': '9007199254740993' if first else '0',
                'total_rewards': '50' if first else '0', 'debt': '30' if first else '0',
                'policy_version': 'C-011-v1-functional-test', 'terms': 'Тестовые условия',
                'history': [{'kind':'referral_reversal','amount':'0','debt_added':'30'}] if first and page == 0 else [],
            })
        defaults = {'/api/v1/settings': {'theme':'dark'}, '/api/v1/wallet': {'available':'0','reserved':'0'},
                    '/api/v1/catalogue': {'models':[],'availability':{}}, '/api/v1/works': {'works':[]}}
        if url.path in defaults:
            return await route.fulfill(json=defaults[url.path])
        await route.fulfill(status=404, body='fixture')

    async with async_playwright() as driver:
        browser = await driver.chromium.launch()
        page = await browser.new_page()
        await page.route('**/*', respond)
        await page.goto('https://referral.fixture/')
        await page.get_by_role('button', name='Приглашения').click()
        await expect(page.locator('#referral-code')).to_have_text('AAAAAAAAAAAAAAAA')
        await page.locator('#load-referral-finances').click()
        await expect(page.locator('#referral-finances-status')).to_contain_text('Не удалось')
        await page.locator('#load-referral-finances').click()
        await expect(page.locator('#referral-finances-summary')).to_contain_text('9007199254740993')
        await expect(page.locator('#referral-finances-history')).to_contain_text('Сторно: 0 · Долг +30')
        await page.locator('#referral-finances-next').click()
        await expect(page.locator('#referral-finances-status')).to_contain_text('нет операций')
        principal = 'second'
        await page.reload()
        await page.get_by_role('button', name='Приглашения').click()
        await expect(page.locator('#referral-code')).to_have_text('BBBBBBBBBBBBBBBB')
        await expect(page.locator('#referral-finances-summary')).to_be_empty()
        await page.locator('#load-referral-finances').click()
        await expect(page.locator('#referral-finances-summary')).to_contain_text('Долг: 0')
        await expect(page.locator('#referral-finances-history')).to_be_empty()
        assert finance_calls == [('first',0),('first',0),('first',1),('second',0)]
        await browser.close()
