"""Headless browser smoke for the local, aggregate-only OB-02 report viewer."""
import json
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / 'docs' / 'demos' / 'ob02-read-model.html'


@pytest.mark.asyncio
async def test_synthetic_sample_and_section_switch(tmp_path):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        try:
            await page.goto(PAGE.as_uri())
            await expect(page.get_by_role('heading', name='Operations report')).to_be_visible()
            await expect(page.locator('#table-title')).to_have_text('Task counts by day and status')

            await page.get_by_role('button', name='Load synthetic sample').click()
            await expect(page.get_by_role('status')).to_contain_text('SYNTHETIC SAMPLE')
            await expect(page.locator('#task-total')).to_have_text('4')
            await expect(page.locator('#table tbody tr')).to_have_count(2)
            await expect(page.locator('#table tbody')).to_contain_text('quoted_task')

            await page.locator('#section').select_option('wallet_movements')
            await expect(page.locator('#table-title')).to_have_text('Wallet ledger movements')
            await expect(page.locator('#table tbody tr')).to_have_count(2)
            await expect(page.locator('#table tbody')).to_contain_text('task_reserve')
            artifact_dir = ROOT / 'artifacts'
            artifact_dir.mkdir(exist_ok=True)
            await page.screenshot(path=str(artifact_dir / 'ob02-report-demo.png'), full_page=True)

            partial = {
                'window': {'start': '2026-11-01T00:00:00+00:00', 'end_exclusive': '2026-11-08T00:00:00+00:00', 'timezone': 'UTC'},
                'tasks_by_period_and_status': {
                    'group_count': 2, 'truncated': True,
                    'groups': [{'source': 'quoted_task', 'status': 'completed', 'task_count': 3}],
                },
                'reconciliation_queue': {
                    'group_count': 2, 'truncated': True,
                    'groups': [{'source': 'task_dispatch', 'status': 'uncertain', 'case_count': 2}],
                },
                'provider_cost_coverage': {
                    'without_operator_cost': 3, 'without_cost_or_bill_evidence': 1, 'accepted_task_count': 4,
                },
            }
            partial_file = tmp_path / 'partial-report.json'
            partial_file.write_text(json.dumps(partial), encoding='utf-8')
            await page.locator('#file').set_input_files(str(partial_file))
            await expect(page.locator('#task-total')).to_have_text('≥ 3')
            await expect(page.locator('#case-total')).to_have_text('≥ 2')
            await expect(page.locator('#partial-note')).to_contain_text('showing 1 of 2 groups')
        finally:
            await browser.close()
