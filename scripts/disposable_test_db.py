"""Fail closed before connecting to the two supported disposable PostgreSQL profiles.

These exact local endpoints are risk reduction, not cryptographic proof of server
identity. Never forward production to a test port; use a dedicated service.
"""
from urllib.parse import urlsplit

_ENDPOINTS = {
    'github-service': ('127.0.0.1:55432', 'fixture-only-disposable'),
    'compose-service': ('127.0.0.1:5432', 'isolated-test-only'),
}
_PG_OVERRIDES = ('PGHOST', 'PGHOSTADDR', 'PGPORT', 'PGDATABASE', 'PGUSER',
                 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS', 'PGPASSFILE')


def require_disposable_dsn(environ):
    """Validate exact URL + profile + explicit confirmation; never echo the URL."""
    try:
        profile = environ.get('DISPOSABLE_POSTGRES_PROFILE', '')
        address, password = _ENDPOINTS[profile]
        raw = environ.get('TEST_DATABASE_URL', '')
        url = urlsplit(raw)
        expected = f'postgres:{password}@{address}'
        if (environ.get('DISPOSABLE_POSTGRES_CONFIRM') != 'YES'
                or url.scheme != 'postgresql' or url.netloc != expected
                or url.path != '/elevenbot_test' or url.query or url.fragment
                or raw != f'postgresql://{expected}/elevenbot_test'
                or environ.get('DATABASE_URL') or environ.get('DATABASE_MIGRATION_URL')
                or any(environ.get(key) for key in _PG_OVERRIDES)):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError('Disposable PostgreSQL test configuration rejected before connection') from None
    return raw
