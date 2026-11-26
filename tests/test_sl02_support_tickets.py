"""The owner-only support candidate uses the disposable PostgreSQL fixture."""

import asyncio
from dataclasses import replace
from uuid import uuid4

import asyncpg
import pytest

from elevenbot.core import Rejected, Service
from elevenbot.support_tickets import SupportTickets


async def test_support_without_consent_is_owner_scoped_and_does_not_move_money(env):
    pool, cfg, _, _ = env
    cfg = replace(cfg, access_mode='private', admin_ids=(100,), pilot_user_ids=(101, 102))
    identity = Service(pool, cfg)
    owner, other = await identity.identity(101), await identity.identity(102)
    assert not await identity.has_current_consent(pool, owner)
    assert not await identity.has_current_consent(pool, other)
    wallets = await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode')
    ledger = await pool.fetch('SELECT * FROM ledger ORDER BY id')
    support = SupportTickets(pool, cfg)

    request = uuid4()
    a, b = await asyncio.gather(*(support.create(101, request, 'Нужна помощь') for _ in range(2)))
    assert a == b and a['status'] == 'open'
    ticket = a['id']
    assert (await support.list(102))['tickets'] == []
    with pytest.raises(Rejected, match='Обращение не найдено'):
        await support.read(102, ticket)
    with pytest.raises(Rejected, match='Обращение не найдено'):
        await support.append(102, ticket, uuid4(), 'Чужое сообщение')
    with pytest.raises(Rejected, match='другим сообщением'):
        await support.create(101, request, 'Подмена')

    reply_request = uuid4()
    replies = await asyncio.gather(*(support.append(101, ticket, reply_request, 'Уточнение') for _ in range(2)))
    assert replies[0] == replies[1]
    first = await support.read(101, ticket, limit=1)
    last = await support.read(101, ticket, limit=1, offset=1)
    assert [first['messages'][0]['body'], last['messages'][0]['body']] == ['Нужна помощь', 'Уточнение']
    assert first['has_more'] and not last['has_more']
    assert await pool.fetchval('SELECT count(*) FROM support_tickets') == 1
    assert await pool.fetchval('SELECT count(*) FROM support_messages') == 2
    assert await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode') == wallets
    assert await pool.fetch('SELECT * FROM ledger ORDER BY id') == ledger


async def test_support_rejects_attachments_unknown_blocked_and_revoked_subjects(env):
    pool, cfg, _, _ = env
    cfg = replace(cfg, access_mode='private', admin_ids=(100,), pilot_user_ids=(101, 102))
    identity = Service(pool, cfg)
    owner = await identity.identity(101)
    support = SupportTickets(pool, cfg)
    with pytest.raises(Rejected, match='Вложения'):
        await support.create(101, uuid4(), 'Описание', attachment=b'fixture')
    for body in ('', ' ' * 5, 'а' * 2001, 'nul\x00'):
        with pytest.raises(Rejected):
            await support.create(101, uuid4(), body)
    with pytest.raises(Rejected):
        await support.list(101, limit=51)
    with pytest.raises(Rejected, match='Поддержка недоступна'):
        await support.create(102, uuid4(), 'Нет записи identity')

    ticket = await support.create(101, uuid4(), 'Настоящий fixture')
    with pytest.raises(asyncpg.RaiseError, match='immutable ledger'):
        await pool.execute("UPDATE support_messages SET body='changed' WHERE ticket_id=$1", ticket['id'])
    with pytest.raises(asyncpg.RaiseError, match='immutable ledger'):
        await pool.execute("DELETE FROM support_tickets WHERE id=$1", ticket['id'])
    with pytest.raises(Rejected, match='Поддержка недоступна'):
        await SupportTickets(pool, replace(cfg, pilot_user_ids=(102,))).read(101, ticket['id'])
    await pool.execute('UPDATE users SET blocked=true WHERE id=$1', owner)
    with pytest.raises(Rejected, match='Поддержка недоступна'):
        await support.append(101, ticket['id'], uuid4(), 'Заблокирован')
    assert await pool.fetchval('SELECT count(*) FROM support_messages') == 1

async def test_telegram_delivers_owner_support_without_purchase_consent(env):
    from elevenbot.telegram import TelegramApp
    from test_admin_access import event
    from test_telegram_consent import DocumentTransport

    pool, cfg, _, _ = env
    cfg = replace(cfg, access_mode='private', admin_ids=(100,), pilot_user_ids=(101,102))
    app = TelegramApp(pool,cfg,DocumentTransport())
    await app.handle(event(501,'/support Синтетическое обращение',chat=101))
    assert 'Обращение принято' in app.bot.sent[-1][0]
    ticket = await pool.fetchval('SELECT id FROM support_tickets')
    await app.handle(event(502,'/support show '+str(ticket),chat=102))
    assert 'Синтетическое обращение' not in app.bot.sent[-1][0]
    await app.handle(event(503,'/support show '+str(ticket),chat=101))
    assert 'Синтетическое обращение' in app.bot.sent[-1][0]
    assert await pool.fetchval('SELECT count(*) FROM support_messages')==1
