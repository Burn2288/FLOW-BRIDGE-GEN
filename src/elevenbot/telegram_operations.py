"""The role-scoped Telegram presentation of existing operator workflows."""

import time
from uuid import UUID, uuid4, uuid5

from .admin_authority import current_capabilities, has_capability
from .core import Rejected
from .operations_objects import MAX_OFFSET, SECTIONS, OperationsDenied, read_objects
from .support_tickets import operator_inbox, operator_reply

PAGE_SIZE = 5
DETAIL_LABELS = {
    'user_id': 'Аккаунт', 'status': 'Статус', 'operation': 'Операция',
    'provider': 'Провайдер', 'created_at': 'Создано', 'blocked': 'Заблокирован',
    'amount': 'Минимальные единицы', 'currency': 'Валюта', 'credits': 'Токены',
    'available': 'Доступно', 'reserved': 'В резерве', 'mode': 'Режим',
    'payment_debt': 'Платёжный долг', 'referral_debt': 'Реферальный долг',
    'visibility': 'Видимость', 'visibility_version': 'Версия видимости',
    'model_id': 'Модель', 'overdue': 'Просрочено', 'health': 'Доступность',
    'kind': 'Тип', 'check': 'Проверка', 'reason': 'Причина',
    'actual': 'Фактически', 'expected': 'Ожидалось',
}


def record_label(row):
    name = next((row[key] for key in ('title','model_id','reason','check','kind','provider') if row.get(key)),
                row.get('user_id',row['id'])[:8])
    status = row.get('status') or row.get('visibility') or row.get('mode')
    return (name + (' · ' + status if status else ''))[:75]


def _detail(value):
    if value == 'NOT_PROVEN':
        return 'Не подтверждено'
    if isinstance(value, bool):
        return 'да' if value else 'нет'
    if isinstance(value, dict):
        return ' · '.join(DETAIL_LABELS.get(key,key) + ': ' + _detail(item) for key,item in value.items())
    return str(value)[:200]


async def show_objects(app, user, external, section, offset=0, *, choice=None):
    from .telegram import buttons

    if app.pool is None:
        raise Rejected('Операторские разделы недоступны.')
    object_id = None
    if choice is not None:
        token, _, index = choice.partition(':')
        pending = app.operation_object_choices.get(external)
        if pending is None or pending[0] != token or pending[1] <= time.monotonic():
            raise Rejected('Список устарел. Откройте /operations.')
        _, _, section, offset, ids = pending
        if not index.isascii() or not index.isdigit() or not 0 <= int(index) < len(ids):
            raise Rejected('Объект недоступен.')
        object_id = ids[int(index)]
    try:
        async with app.pool.acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
            result = await read_objects(conn,user,app.providers,section,object_id=object_id,
                                        offset=0 if object_id else offset,limit=PAGE_SIZE)
    except OperationsDenied:
        app.operation_object_choices.pop(external,None)
        raise Rejected('Операторские разделы недоступны.') from None
    except (KeyError,ValueError):
        raise Rejected('Выберите раздел в /operations.') from None
    if result is None:
        raise Rejected('Объект больше недоступен.')

    rows = []
    if object_id is not None:
        lines = [SECTIONS[section],record_label(result)]
        lines.extend(DETAIL_LABELS.get(key,key) + ': ' + _detail(value) for key,value in result.items()
                     if value is not None and key not in ('id','title'))
        rows.append([('← К списку',f'opobjects:{section}:{offset}')])
    else:
        token = uuid4().hex
        app.operation_object_choices[external] = (token,time.monotonic()+300,section,offset,
                                                   [row['id'] for row in result['items']])
        lines = [SECTIONS[section]]
        if not result['items']:
            lines.append('Записей пока нет.')
        if result['truncated']:
            lines.append('Показаны первые случаи каждой проверки.')
        for index,row in enumerate(result['items']):
            rows.append([(record_label(row),f'opobject:{token}:{index}')])
        page = []
        if offset:
            page.append(('← Ранее',f'opobjects:{section}:{max(0,offset-PAGE_SIZE)}'))
        if result['has_more'] and offset+PAGE_SIZE<=MAX_OFFSET:
            page.append(('Далее →',f'opobjects:{section}:{offset+PAGE_SIZE}'))
        if page:
            rows.append(page)
    rows.append([('← Обзор операций','opoverview')])
    await app.catalogue_screen(external,'\n'.join(lines),buttons(rows),panel='operations')


async def show_support(app,user,external,ticket=None):
    from .telegram import buttons

    if app.pool is None:
        raise Rejected('Очередь поддержки недоступна.')
    async with app.pool.acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
        if not has_capability(await current_capabilities(conn,user),'support.operate'):
            raise Rejected('Очередь поддержки недоступна.')
        result = await operator_inbox(conn,ticket)
    if result is None:
        raise Rejected('Обращение не найдено.')
    if ticket is None:
        rows = [[(f"{str(row['id'])[:8]} · {row['status']}",f'ophelp:{row["id"]}')]
                for row in result['tickets'][:10]]
        text = 'Последние обращения поддержки' if rows else 'Обращений нет.'
    else:
        rows = [[('← Обращения','ophelp')]]
        messages = '\n'.join(
            ('Оператор: ' if row['author']=='operator' else 'Пользователь: ') + row['body']
            for row in result['messages'][-3:]
        )[-2400:]
        text = f"Обращение {ticket} · {result['status']}\n\n{messages}\n\nОтвет: /operator_reply {ticket} текст"
    await app.catalogue_screen(external,text,buttons(rows) if rows else None,panel='operator_support')


async def reply_support(app,user,external,text,update_id):
    if app.pool is None:
        raise Rejected('Ответ оператора недоступен.')
    parts = text.split(maxsplit=2)
    if len(parts) != 3:
        raise Rejected('Формат: /operator_reply ИДЕНТИФИКАТОР текст.')
    try:
        ticket = UUID(parts[1])
    except ValueError:
        raise Rejected('Обращение не найдено.') from None
    async with app.pool.acquire() as conn, conn.transaction():
        saved = await operator_reply(conn,user,ticket,uuid5(user,'telegram-operator-reply:'+str(update_id)),parts[2])
    if saved is None:
        raise Rejected('Обращение не найдено.')
    await show_support(app,user,external,ticket)
