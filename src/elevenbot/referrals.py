"""Stable referral codes and first-registration attribution, without rewards."""
import re
import secrets

from .core import Rejected

CODE = re.compile(r'^[A-Za-z0-9_-]{16}$', re.ASCII)


def start_code(text):
    if not isinstance(text, str):
        return None
    parts = text.strip().split()
    if len(parts) != 2 or parts[0].lower().partition('@')[0] != '/start' or not parts[1].startswith('ref_'):
        return None
    candidate = parts[1][4:]
    return candidate if CODE.fullmatch(candidate) else None


async def attribute_new_user(conn, user, code):
    if not isinstance(code, str) or not CODE.fullmatch(code):
        return
    await conn.execute('''INSERT INTO referral_attributions(user_id,referrer_id)
        SELECT $1,user_id FROM referral_codes WHERE code=$2 AND user_id<>$1
        ON CONFLICT(user_id) DO NOTHING''', user, code)


async def own_info(service, user):
    async with service.pool.acquire() as conn, conn.transaction():
        await service.authorize(conn, user)
        for _ in range(8):
            existing = await conn.fetchval('SELECT code FROM referral_codes WHERE user_id=$1', user)
            if existing:
                break
            # ON CONFLICT handles both a collision and concurrent issuance without
            # putting the transaction into PostgreSQL's aborted state.
            candidate = secrets.token_urlsafe(12)
            existing = await conn.fetchval('''INSERT INTO referral_codes(user_id,code)
                VALUES($1,$2) ON CONFLICT DO NOTHING RETURNING code''', user, candidate)
            if existing:
                break
        else:
            raise Rejected('Не удалось получить код приглашения. Попробуйте позже.')
        referred = await conn.fetchval('SELECT EXISTS(SELECT 1 FROM referral_attributions WHERE user_id=$1)', user)
        return {'code': existing, 'has_referrer': referred}

async def own_finances(service, user, page):
    """Read an authorized user's own reward events on a single snapshot."""
    if type(page) is not int or not 0 <= page <= 1000:
        raise ValueError('Invalid referral history page')
    info = await own_info(service, user)
    async with service.pool.acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
        await service.authorize(conn, user)
        summary = await conn.fetchrow("""
            WITH own AS (
                SELECT * FROM referral_rewards WHERE referrer_id=$1
            )
            SELECT
                (SELECT count(*) FROM referral_attributions WHERE referrer_id=$1) AS invitee_count,
                (SELECT coalesce(sum(available),0) FROM wallet_funding_lots
                 WHERE user_id=$1 AND mode='live' AND origin='REFERRAL') AS available,
                (SELECT coalesce(sum(amount),0) FROM own) AS earned,
                (SELECT coalesce(sum(v.debt_added),0) FROM referral_reversals v JOIN own USING(capture_id))
                - (SELECT coalesce(sum(p.amount),0) FROM referral_debt_repayments p JOIN own USING(capture_id)) AS debt
        """, user)
        rows = await conn.fetch("""
            SELECT l.created_at,l.kind,l.da,p.policy_version
            FROM ledger l JOIN referral_rewards r ON r.referrer_id=$1
            JOIN referral_policy_snapshots p ON p.reserve_ledger_id=r.reserve_id
            LEFT JOIN referral_reversals v ON v.capture_id=r.capture_id
            LEFT JOIN referral_debt_repayments d ON d.capture_id=r.capture_id
            WHERE l.user_id=$1 AND l.id IN (r.reward_ledger_id,v.ledger_id,d.ledger_id)
            ORDER BY l.created_at DESC,l.id DESC LIMIT 11 OFFSET $2
        """, user, page * 10)
    return {**info, 'invitee_count': summary['invitee_count'],
            'available': str(summary['available']), 'total_rewards': str(summary['earned']),
            'debt': str(summary['debt']), 'policy_version': 'C-011-v1-functional-test',
            'page': page, 'has_more': len(rows) > 10,
            'history': [{'at': row['created_at'].isoformat(), 'kind': row['kind'],
                         'amount': str(row['da']), 'policy_version': row['policy_version']}
                        for row in rows[:10]]}
