"""Shared test consent documents and version for Telegram and Mini App."""
from importlib.resources import files

# Change together with both documents, after coordinating all direct SQL readers.
CURRENT_VERSION = '1'
LEGACY_VERSION = '1'


def documents():
    legal = files('elevenbot').joinpath('legal')
    return {'version': CURRENT_VERSION,
            'terms': legal.joinpath('terms.md').read_text(encoding='utf-8'),
            'privacy': legal.joinpath('privacy.md').read_text(encoding='utf-8'),
            'test_only': True}


async def is_current(conn, user_id):
    return bool(await conn.fetchval(
        'SELECT EXISTS(SELECT 1 FROM identities WHERE user_id=$1 AND terms_version=$2 AND accepted_at IS NOT NULL)',
        user_id, CURRENT_VERSION))
