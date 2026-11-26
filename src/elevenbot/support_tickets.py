"""Owner-only support candidate. Call only with a verified transport subject."""

from uuid import UUID

from .admission import admitted
from .core import Rejected


class SupportTickets:
    """Text support for existing identities, without a financial or operator API."""

    def __init__(self, pool, config):
        self.pool = pool
        self.config = config

    async def _owner(self, conn, subject, platform, *, lock=False):
        if (platform not in ('telegram', 'max') or type(subject) is not int
                or not 0 < subject <= 2**63 - 1 or not admitted(self.config, subject, platform)):
            raise Rejected('Поддержка недоступна.')
        sql = """SELECT i.user_id FROM identities i JOIN users u ON u.id=i.user_id
                 WHERE i.platform=$1 AND i.external_id=$2 AND NOT u.blocked"""
        owner = await conn.fetchval(sql + (' FOR SHARE OF u' if lock else ''), platform, subject)
        if owner is None:
            raise Rejected('Поддержка недоступна.')
        return owner

    @staticmethod
    def _text(body, attachment):
        if attachment is not None:
            raise Rejected('Вложения пока недоступны.')
        if not isinstance(body, str) or not 1 <= len(body) <= 2000:
            raise Rejected('Введите от 1 до 2000 символов.')
        body = body.strip()
        if not body or any(ord(char) < 32 and char not in '\n\t' for char in body):
            raise Rejected('Недопустимый текст обращения.')
        return body

    @staticmethod
    def _id(value):
        if not isinstance(value, UUID):
            raise Rejected('Недопустимый идентификатор обращения.')
        return value

    @staticmethod
    def _page(limit, offset):
        if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or not 0 <= offset <= 5000:
            raise Rejected('Недопустимая страница обращений.')
        return limit + 1, offset

    @staticmethod
    async def _message(conn, ticket, request_id, body):
        row = await conn.fetchrow("""INSERT INTO support_messages(ticket_id,request_id,body)
            VALUES($1,$2,$3) ON CONFLICT (ticket_id,request_id) DO NOTHING
            RETURNING id,body,created_at""", ticket, request_id, body)
        if row is None:
            row = await conn.fetchrow("""SELECT id,body,created_at FROM support_messages
                WHERE ticket_id=$1 AND request_id=$2""", ticket, request_id)
            if row['body'] != body:
                raise Rejected('Этот идентификатор уже использован с другим сообщением.')
        return dict(row)

    @staticmethod
    async def _ticket(conn, owner, ticket_id):
        ticket = await conn.fetchrow("""SELECT id,status,created_at FROM support_tickets
            WHERE owner_id=$1 AND id=$2""", owner, ticket_id)
        if ticket is None:
            raise Rejected('Обращение не найдено.')
        return dict(ticket)

    async def create(self, subject, request_id, body, *, platform='telegram', attachment=None):
        request_id, body = self._id(request_id), self._text(body, attachment)
        async with self.pool.acquire() as conn, conn.transaction():
            owner = await self._owner(conn, subject, platform, lock=True)
            ticket = await conn.fetchrow("""INSERT INTO support_tickets(owner_id,request_id) VALUES($1,$2)
                ON CONFLICT(owner_id,request_id) DO NOTHING RETURNING id,status,created_at""", owner, request_id)
            if ticket is None:
                ticket = await conn.fetchrow("""SELECT id,status,created_at FROM support_tickets
                    WHERE owner_id=$1 AND request_id=$2""", owner, request_id)
            message = await self._message(conn, ticket['id'], request_id, body)
            return {**dict(ticket), 'message': message}

    async def append(self, subject, ticket, request_id, body, *, platform='telegram', attachment=None):
        ticket, request_id, body = self._id(ticket), self._id(request_id), self._text(body, attachment)
        async with self.pool.acquire() as conn, conn.transaction():
            owner = await self._owner(conn, subject, platform, lock=True)
            await self._ticket(conn, owner, ticket)
            return await self._message(conn, ticket, request_id, body)

    async def list(self, subject, *, platform='telegram', limit=20, offset=0):
        count, offset = self._page(limit, offset)
        async with self.pool.acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
            owner = await self._owner(conn, subject, platform)
            rows = await conn.fetch("""SELECT id,status,created_at FROM support_tickets
                WHERE owner_id=$1 ORDER BY created_at DESC,id DESC LIMIT $2 OFFSET $3""",
                owner, count, offset)
        return {'tickets': [dict(row) for row in rows[:limit]], 'has_more': len(rows) > limit}

    async def read(self, subject, ticket, *, platform='telegram', limit=20, offset=0):
        ticket = self._id(ticket)
        count, offset = self._page(limit, offset)
        async with self.pool.acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
            owner = await self._owner(conn, subject, platform)
            owned = await self._ticket(conn, owner, ticket)
            rows = await conn.fetch("""SELECT * FROM (
                    SELECT id,body,created_at,'owner' AS author FROM support_messages WHERE ticket_id=$1
                    UNION ALL
                    SELECT id,body,created_at,'operator' FROM support_operator_replies WHERE ticket_id=$1
                ) timeline ORDER BY created_at,id LIMIT $2 OFFSET $3""", ticket, count, offset)
        return {**owned, 'messages': [dict(row) for row in rows[:limit]], 'has_more': len(rows) > limit}

async def operator_reply(conn, actor, ticket, request_id, text):
    """The caller supplies a transaction with an authenticated, locked authority."""
    if not conn.is_in_transaction():
        raise RuntimeError('support reply requires a transaction')
    from .admin_authority import current_capabilities, has_capability
    await conn.execute('LOCK TABLE http_admin_role_events IN SHARE MODE')
    if not has_capability(await current_capabilities(conn, actor), 'support.operate'):
        raise Rejected('Ответ оператора недоступен.')
    body = SupportTickets._text(text,None)
    if not await conn.fetchval('SELECT EXISTS(SELECT 1 FROM support_tickets WHERE id=$1)',ticket):
        return None
    inserted = await conn.fetchval("""
        INSERT INTO support_operator_replies(ticket_id,actor_id,request_id,body)
        VALUES($1,$2,$3,$4) ON CONFLICT(ticket_id,request_id) DO NOTHING RETURNING id
    """,ticket,actor,request_id,body)
    if inserted:
        return inserted
    old = await conn.fetchrow("""
        SELECT id,actor_id,body FROM support_operator_replies WHERE ticket_id=$1 AND request_id=$2
    """,ticket,request_id)
    if (old['actor_id'],old['body']) != (actor,body):
        raise Rejected('Конфликт повторного ответа.')
    return old['id']
