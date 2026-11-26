"""Owner-approved 2/3-token FLUX tariff for the isolated functional test."""

from decimal import Decimal
import os
from uuid import UUID

from .admin_authority import current_capabilities, has_capability
from .pricing import BOT_TOKEN, POLICY_LOCK, PriceUnavailable, Pricing, Request


class TariffDenied(Exception):
    pass


class TariffConflict(Exception):
    pass


CAPABILITY = 'pricing.publish_fixture'
_DEV_DSN = 'postgresql://postgres:isolated-test-only@127.0.0.1:5432/flowbridge_dev'
_REQUEST = Request('clodex', 'flux-schnell', 'images.generate', 'FLUX Schnell',
                   'Функциональный тест тарифа', {'n': 1})
_KEY = (_REQUEST.provider, _REQUEST.model, _REQUEST.operation, '{"n":1}')


def fixture_profile():
    if os.environ.get('PC02_FUNCTIONAL_TEST') != 'YES':
        return None
    if (os.environ.get('FLOWBRIDGE_DEV_FIXTURE') == 'YES'
            and os.environ.get('DATABASE_URL') == _DEV_DSN
            and not os.environ.get('DATABASE_MIGRATION_URL')
            and not os.environ.get('TEST_DATABASE_URL')):
        return 'flowbridge_dev'
    from scripts.disposable_test_db import require_disposable_dsn
    try:
        require_disposable_dsn(os.environ)
    except ValueError:
        return None
    return 'elevenbot_test'


async def authorize(conn, actor):
    profile = fixture_profile()
    if profile is None:
        raise TariffDenied()
    if profile == 'flowbridge_dev':
        isolated = await conn.fetchval("""
            SELECT current_database()='flowbridge_dev' AND session_user='postgres'
                AND inet_server_addr()='127.0.0.1'::inet AND inet_server_port()=5432
        """)
    else:
        isolated = await conn.fetchval("SELECT current_database()='elevenbot_test'")
    if not isolated or not has_capability(await current_capabilities(conn, actor), CAPABILITY):
        raise TariffDenied()


def _typed(amount, rollback_of):
    if type(amount) is not int or amount != (3 if rollback_of is None else 2):
        raise ValueError('Invalid fixture tariff amount')
    if rollback_of is not None and (type(rollback_of) is not int or not 0 < rollback_of < 2**63):
        raise ValueError('Invalid rollback version')


def _audit(event):
    if event is None:
        return None
    return {
        'version': event['version'], 'previous_amount': event['previous_amount'],
        'amount': event['amount'], 'rollback_of': event['rollback_of'],
        'actor_id': str(event['actor_id']), 'recorded_at': event['recorded_at'].isoformat(),
    }


def _public(amount, version, event):
    return {
        'provider': _REQUEST.provider, 'model_id': _REQUEST.model,
        'operation': _REQUEST.operation, 'params': dict(_REQUEST.params),
        'unit': BOT_TOKEN, 'basis': 'request', 'amount': amount, 'sale_amount': amount,
        'version': version, 'previous_amount': event['previous_amount'] if event else None,
        'audit': _audit(event),
    }


async def _effective(conn, pricing, manual, amount):
    # Reuse the quote calculation, including any applicable markup and conversion.
    cost = pricing.manual_price(_REQUEST, dict(manual) | {'amount': Decimal(amount)})
    try:
        result = await pricing.calculate(conn, _REQUEST, cost)
    except PriceUnavailable:
        raise TariffConflict() from None
    if Decimal(result['base']) != amount or int(result['total']) != amount:
        raise TariffConflict()


async def _current(conn, pricing):
    row = await pricing.manual_row(conn, _REQUEST)
    if (row is None or not row['active'] or row['temporary'] or row['expires_at'] is not None
            or row['basis'] != 'request' or row['source_unit'] != BOT_TOKEN
            or row['output_amount'] is not None or row['amount'] not in (2, 3)):
        raise TariffConflict()
    amount = int(row['amount'])
    await _effective(conn, pricing, row, amount)
    event = await conn.fetchrow('SELECT * FROM fixture_tariff_events WHERE version=$1', row['revision'])
    return row, _public(amount, row['revision'], event)


async def get(conn, actor):
    await authorize(conn, actor)
    _, current = await _current(conn, Pricing(None, None, {}))
    return current


def _valid_transition(current, amount, rollback_of):
    if amount == current['amount']:
        raise TariffConflict()
    if rollback_of is not None and (
        rollback_of != current['version'] or current['previous_amount'] != amount
    ):
        raise TariffConflict()


async def preview(conn, actor, amount, rollback_of=None):
    await authorize(conn, actor)
    _typed(amount, rollback_of)
    pricing = Pricing(None, None, {})
    row, current = await _current(conn, pricing)
    _valid_transition(current, amount, rollback_of)
    await _effective(conn, pricing, row, amount)
    return {**current, 'desired_amount': amount, 'desired_sale_amount': amount, 'rollback_of': rollback_of}


async def confirm(conn, actor, amount, expected_version, request_id, rollback_of=None):
    """Publish and append the audit event in the caller's transaction."""
    if not conn.is_in_transaction():
        raise RuntimeError('Fixture tariff confirmation requires a transaction')
    _typed(amount, rollback_of)
    if type(expected_version) is not int or not 0 < expected_version < 2**63 or not isinstance(request_id, UUID):
        raise ValueError('Invalid fixture tariff confirmation')
    await conn.execute('LOCK TABLE http_admin_role_events IN SHARE MODE')
    await conn.fetchval('SELECT 1 FROM users WHERE id=$1 FOR SHARE', actor)
    await authorize(conn, actor)
    await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)', POLICY_LOCK)
    replay = await conn.fetchrow('SELECT * FROM fixture_tariff_events WHERE request_id=$1', request_id)
    if replay is not None:
        if (replay['actor_id'], replay['amount'], replay['expected_version'], replay['rollback_of']) != (
            actor, amount, expected_version, rollback_of
        ):
            raise TariffConflict()
        return _public(amount, replay['version'], replay)

    pricing = Pricing(None, None, {})
    row, current = await _current(conn, pricing)
    if current['version'] != expected_version:
        raise TariffConflict()
    _valid_transition(current, amount, rollback_of)
    await _effective(conn, pricing, row, amount)
    version = await conn.fetchval("""
        UPDATE task_manual_tariffs SET amount=$5, revision=nextval('task_price_rule_revision'),
            admin_id=$6, verified_at=clock_timestamp()
        WHERE (provider,model_id,operation,params)=($1,$2,$3,$4::jsonb) AND revision=$7
        RETURNING revision
    """, *_KEY, Decimal(amount), actor, expected_version)
    if version is None:
        raise TariffConflict()
    event = await conn.fetchrow("""
        INSERT INTO fixture_tariff_events
            (version,expected_version,request_id,actor_id,previous_amount,amount,rollback_of)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        RETURNING *
    """, version, expected_version, request_id, actor, current['amount'], amount, rollback_of)
    return _public(amount, version, event)
