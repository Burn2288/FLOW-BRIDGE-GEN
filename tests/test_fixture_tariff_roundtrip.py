"""PC-02 gated publication, immutable quotes, and both product entrypoints."""

import asyncio
from uuid import UUID, uuid4

import asyncpg
import pytest

from miniapp.tests.test_miniapp import account_db
from test_admin_access import event
from test_ft020_http_image import TEST_VIEW, create, image_api


ADMIN_TARIFF = '/api/v1/admin/flux-tariff'


async def test_fixture_tariff_roundtrip(image_api, monkeypatch):
    pool, users, client, headers, posts, deferred, _, _ = image_api
    monkeypatch.setenv('PC02_FUNCTIONAL_TEST', 'YES')
    operator, ordinary = users
    admin_headers, ordinary_headers = headers
    telegram = client.app[TEST_VIEW]
    await telegram.pricing.set_tariff(
        operator, 100, 'clodex', 'flux-schnell', 'images.generate', {'n': 1},
        basis='request', unit='darkflow_token', amount='2', expires=None, evidence='fixture',
    )

    async def role(value):
        await pool.execute("""
            INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
            VALUES($1,$1,$2,'synthetic tariff regression')
        """, operator, value)

    async def priced_state():
        return (
            await pool.fetch('SELECT * FROM task_manual_tariffs ORDER BY provider,model_id,operation'),
            await pool.fetch('SELECT * FROM task_price_quotes ORDER BY id'),
            await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode'),
            await pool.fetch('SELECT * FROM ledger ORDER BY id'),
            await pool.fetch('SELECT * FROM task_dispatch ORDER BY quote_id'),
        )

    def callback(prefix):
        return next(item.callback_data for _, keyboard in reversed(telegram.bot.sent)
                    if hasattr(keyboard, 'inline_keyboard')
                    for row in keyboard.inline_keyboard for item in row
                    if (item.callback_data or '').startswith(prefix))

    update_id = 1500

    async def telegram_input(text=None, button=None):
        nonlocal update_id
        update_id += 1
        await telegram.handle(event(update_id, text, chat=101, callback=button))

    async def telegram_quote(prompt, amount):
        version = telegram.catalogue_snapshot()['version']
        await telegram_input(button=f'smodel:{version}:image:0:0')
        await telegram_input(button=callback('srun:'))
        previous_message_count = len(telegram.bot.sent)
        await telegram_input(text=prompt)
        assert len(telegram.bot.sent) > previous_message_count
        assert f'Оценка: {amount} ' in telegram.bot.sent[-1][0]
        confirm = callback('amconfirm:')
        return UUID(confirm.split(':')[1]), confirm

    async def miniapp_quote(prompt, amount):
        response = await client.post('/api/v1/quotes', headers=admin_headers,
                                     json={'model': 'flux-schnell', 'prompt': prompt})
        assert response.status == 201, await response.text()
        quoted = await response.json()
        assert quoted['price']['total'] == str(amount)
        return UUID(quoted['quote_id'])

    async def settle_pair(telegram_job, telegram_button, miniapp_job, amount):
        await telegram_input(button=telegram_button)
        created = await create(client, admin_headers, str(miniapp_job), str(miniapp_job))
        assert created.status == 201, await created.text()
        replay = await create(client, admin_headers, str(miniapp_job), str(miniapp_job))
        assert replay.status == 200 and (await replay.json())['id'] == str(miniapp_job)
        assert len(deferred) == 1
        await deferred.pop()()
        for job, owner in ((telegram_job, ordinary), (miniapp_job, operator)):
            assert tuple(await pool.fetchrow(
                "SELECT state,price->>'total' FROM task_price_quotes WHERE id=$1", job,
            )) == ('accepted', str(amount))
            assert [tuple(row) for row in await pool.fetch("""
                SELECT user_id,kind,da,dr FROM ledger WHERE task_quote_id=$1 ORDER BY kind
            """, job)] == [(owner, 'task_capture', 0, -amount), (owner, 'task_reserve', -amount, amount)]

    assert (await client.get(ADMIN_TARIFF)).status == 401
    assert (await client.get(ADMIN_TARIFF, headers=admin_headers)).status == 403
    await role('READ_ONLY_ADMIN')
    assert (await client.post(ADMIN_TARIFF+'/preview', headers=admin_headers, json={'amount': 3})).status == 403
    await role('OWNER_ADMIN')
    assert (await client.get(ADMIN_TARIFF, headers=ordinary_headers)).status == 403
    monkeypatch.delenv('PC02_FUNCTIONAL_TEST')
    assert (await client.get(ADMIN_TARIFF, headers=admin_headers)).status == 403
    monkeypatch.setenv('PC02_FUNCTIONAL_TEST', 'YES')
    state = await client.get(ADMIN_TARIFF, headers=admin_headers)
    assert state.status == 200, await state.text()
    current = await state.json()
    assert (current['amount'], current['sale_amount'], current['unit'], current['params'], current['audit']) == (
        2, 2, 'darkflow_token', {'n': 1}, None,
    )
    old_telegram_quote, old_telegram_button = await telegram_quote('Telegram priced before publication', 2)
    old_miniapp_quote = await miniapp_quote('Mini App priced before publication', 2)
    before = await priced_state()

    invalid = await client.post(ADMIN_TARIFF+'/preview', headers=admin_headers,
                                json={'amount': 3, 'model_id': 'outside-approved-scope'})
    assert invalid.status == 400
    preview = await client.post(ADMIN_TARIFF+'/preview', headers=admin_headers, json={'amount': 3})
    assert preview.status == 200, await preview.text()
    draft = await preview.json()
    assert (draft['amount'], draft['desired_amount']) == (2, 3)
    assert await priced_state() == before
    assert not await pool.fetchval('SELECT count(*) FROM fixture_tariff_events')
    assert not posts and not deferred

    command = {'amount': 3, 'expected_version': draft['version'], 'request_id': str(uuid4())}
    first, second = await asyncio.gather(*(
        client.post(ADMIN_TARIFF+'/confirm', headers=admin_headers, json=command) for _ in range(2)
    ))
    assert first.status == second.status == 200, (await first.text(), await second.text())
    published = await first.json()
    assert published == await second.json()
    assert published['amount'] == 3 and published['version'] != draft['version']
    assert (await priced_state())[1:] == before[1:]
    stale = await client.post(ADMIN_TARIFF+'/confirm', headers=admin_headers,
                              json=command | {'request_id': str(uuid4())})
    assert stale.status == 409
    changed_replay = await client.post(ADMIN_TARIFF+'/confirm', headers=admin_headers,
                                       json=command | {'expected_version': published['version']})
    assert changed_replay.status == 409

    await settle_pair(old_telegram_quote, old_telegram_button, old_miniapp_quote, 2)
    new_telegram_quote, new_telegram_button = await telegram_quote('Telegram after publication', 3)
    new_miniapp_quote = await miniapp_quote('Mini App after publication', 3)
    await settle_pair(new_telegram_quote, new_telegram_button, new_miniapp_quote, 3)
    assert posts == ['/v1/images/generations'] * 4
    for actor in (ordinary, operator):
        assert tuple(await pool.fetchrow("""
            SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'
        """, actor)) == (95, 0)

    rollback = {'amount': 2, 'rollback_of': published['version']}
    before_rollback = await priced_state()
    preview = await client.post(ADMIN_TARIFF+'/preview', headers=admin_headers, json=rollback)
    assert preview.status == 200, await preview.text()
    assert await priced_state() == before_rollback
    rollback_draft = await preview.json()
    rollback.update(expected_version=rollback_draft['version'], request_id=str(uuid4()))
    restored = await client.post(ADMIN_TARIFF+'/confirm', headers=admin_headers, json=rollback)
    assert restored.status == 200, await restored.text()
    restored = await restored.json()
    assert restored['amount'] == 2 and restored['version'] != published['version']
    assert restored['audit']['actor_id'] == str(operator)
    assert restored['audit']['rollback_of'] == published['version']
    assert (await priced_state())[1:] == before_rollback[1:]
    reopened = await client.post(ADMIN_TARIFF+'/confirm', headers=admin_headers, json=rollback)
    assert reopened.status == 200 and await reopened.json() == restored
    history = await pool.fetch("""
        SELECT version,expected_version,actor_id,previous_amount,amount,rollback_of,request_id
        FROM fixture_tariff_events ORDER BY version
    """)
    assert [tuple(row) for row in history] == [
        (published['version'], draft['version'], operator, 2, 3, None, UUID(command['request_id'])),
        (restored['version'], published['version'], operator, 3, 2, published['version'],
         UUID(rollback['request_id'])),
    ]
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute('UPDATE fixture_tariff_events SET amount=previous_amount')
    await telegram_quote('Telegram after rollback', 2)
    await miniapp_quote('Mini App after rollback', 2)

    await role(None)
    before_denial = await priced_state()
    assert (await client.post(ADMIN_TARIFF+'/confirm', headers=admin_headers, json=rollback)).status == 403
    assert (await client.get(ADMIN_TARIFF, headers=admin_headers)).status == 403
    assert await priced_state() == before_denial
    assert await pool.fetchval('SELECT count(*) FROM fixture_tariff_events') == 2
