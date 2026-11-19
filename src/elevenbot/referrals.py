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
