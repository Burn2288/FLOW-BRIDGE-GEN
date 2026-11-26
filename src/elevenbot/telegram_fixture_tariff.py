"""Telegram presentation for the single owner-approved fixture tariff."""

import time
from uuid import uuid4

from . import fixture_tariff
from .core import Rejected


async def show(app, user, external, action='fluxtariff', value=''):
    from .telegram import buttons

    if app.pool is None:
        raise Rejected('Тестовый тариф доступен только владельцу стенда.')
    notice = ''
    try:
        async with app.pool.acquire() as conn:
            if action == 'fluxtariffpreview':
                state = await fixture_tariff.get(conn, user)
                if value == 'publish':
                    amount, rollback_of, label = 3, None, 'публикацию'
                elif value == 'rollback':
                    amount, rollback_of, label = 2, state['version'], 'откат'
                else:
                    raise ValueError()
                result = await fixture_tariff.preview(conn, user, amount, rollback_of=rollback_of)
                event = uuid4()
                app.fixture_tariff_previews[external] = (event, time.monotonic()+300, result)
            elif action == 'fluxtariffconfirm':
                item = app.fixture_tariff_previews.get(external)
                if item is None or str(item[0]) != value or item[1] <= time.monotonic():
                    raise Rejected('Предпросмотр устарел. Откройте /flux_tariff.')
                event, _, draft = item
                async with conn.transaction():
                    result = await fixture_tariff.confirm(conn,user,draft['desired_amount'],draft['version'],
                        event,rollback_of=draft['rollback_of'])
                notice = 'Тариф восстановлен.\n' if draft['rollback_of'] else 'Тариф опубликован.\n'
            else:
                result = await fixture_tariff.get(conn, user)
    except fixture_tariff.TariffDenied:
        app.fixture_tariff_previews.pop(external, None)
        raise Rejected('Тестовый тариф доступен только владельцу стенда.') from None
    except (fixture_tariff.TariffConflict, ValueError):
        app.fixture_tariff_previews.pop(external, None)
        raise Rejected('Версия или состояние тарифа изменились. Откройте новый предпросмотр.') from None

    heading = 'Тестовый тариф FLUX Schnell\nimages.generate · n=1 · за запрос'
    if action == 'fluxtariffpreview':
        text = (f"{heading}\nПредпросмотр · {result['amount']} → {result['desired_amount']} токена\n"
                f"Текущая версия: {result['version']}")
        rows = [[(f'Подтвердить {label}', f'fluxtariffconfirm:{event}')],
                [('Отменить предпросмотр', 'fluxtariff')]]
    else:
        text = f"{notice}{heading}\n{result['amount']} токена · версия {result['version']}"
        event_data = result.get('audit')
        if event_data is None:
            text += '\nПубликаций пока нет.'
        else:
            text += (f"\nАудит · версия {event_data['version']} · "
                     f"{event_data['previous_amount']} → {event_data['amount']} · "
                     f"оператор {event_data['actor_id']} · {event_data['recorded_at']}")
            if event_data['rollback_of']:
                text += f"\nОткат версии {event_data['rollback_of']}."
        rows = [[('Предпросмотр отката', 'fluxtariffpreview:rollback')]] if result['amount'] == 3 else [
            [('Предпросмотр публикации', 'fluxtariffpreview:publish')]
        ]
    rows.append([('← Обзор операций', 'opoverview')])
    await app.catalogue_screen(external,text,buttons(rows),panel='fixture_tariff')
    if action != 'fluxtariffpreview':
        app.fixture_tariff_previews.pop(external, None)
