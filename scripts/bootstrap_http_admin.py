"""Bootstrap an explicitly owner-approved existing Telegram identity in an isolated test database."""
import argparse
import asyncio
import os

import asyncpg

from scripts.disposable_test_db import require_disposable_dsn


async def bootstrap(external_id, approval):
    conn = await asyncpg.connect(require_disposable_dsn(os.environ))
    try:
        async with conn.transaction():
            await conn.execute('LOCK TABLE http_admin_role_events IN SHARE ROW EXCLUSIVE MODE')
            if await conn.fetchval('SELECT EXISTS(SELECT 1 FROM http_admin_role_events)'):
                raise ValueError('HTTP authority already initialized')
            user = await conn.fetchval("""
                SELECT i.user_id FROM identities i JOIN users u ON u.id=i.user_id
                WHERE i.platform='telegram' AND i.external_id=$1 AND NOT u.blocked
            """, external_id)
            if user is None:
                raise ValueError('Approved identity is missing or blocked')
            await conn.execute("""
                INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason)
                VALUES($1,$1,'OWNER_ADMIN',$2)
            """, user, approval)
    finally:
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-telegram-id', type=int, required=True)
    parser.add_argument('--owner-approval-reference', required=True)
    args = parser.parse_args()
    if not 0 < args.approved_telegram_id <= 2**63-1 or not 1 <= len(args.owner_approval_reference.strip()) <= 200:
        parser.error('Invalid identity or approval reference')
    asyncio.run(bootstrap(args.approved_telegram_id, args.owner_approval_reference.strip()))
