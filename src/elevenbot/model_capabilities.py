"""Versioned rules attached to existing admitted provider/model/operation keys."""
import json
import re
from uuid import uuid4

from .core import Rejected

FLUX_MODEL = 'flux-schnell'
POLICY_LOCK = 921189
NAME = re.compile(r'^[a-z][a-z0-9_]{0,63}$')


def validate_schema(schema):
    if not isinstance(schema, dict) or set(schema) != {'properties', 'required'}:
        raise Rejected('Некорректная схема параметров модели.')
    props, required = schema['properties'], schema['required']
    if not isinstance(props, dict) or len(props) > 30 or not isinstance(required, list):
        raise Rejected('Некорректная схема параметров модели.')
    if any(not isinstance(k, str) or not NAME.fullmatch(k) for k in props):
        raise Rejected('Некорректная схема параметров модели.')
    if any(not isinstance(k, str) or k not in props for k in required) or len(required) != len(set(required)):
        raise Rejected('Некорректная схема параметров модели.')
    for spec in props.values():
        if not isinstance(spec, dict) or set(spec) - {'type', 'minimum', 'maximum'} or spec.get('type') != 'integer':
            raise Rejected('Поддерживаются только целочисленные параметры.')
        if any(type(spec[k]) is not int for k in ('minimum', 'maximum') if k in spec):
            raise Rejected('Некорректные границы параметров.')
        if 'minimum' in spec and 'maximum' in spec and spec['minimum'] > spec['maximum']:
            raise Rejected('Некорректные границы параметров.')
    return schema


def validate_params(schema, params):
    validate_schema(schema)
    props = schema['properties']
    if not isinstance(params, dict) or set(params) - set(props) or set(schema['required']) - set(params):
        raise Rejected('Недопустимые параметры модели.')
    for key, value in params.items():
        spec = props[key]
        if type(value) is not int or value < spec.get('minimum', value) or value > spec.get('maximum', value):
            raise Rejected('Недопустимые параметры модели.')


async def published_version(conn, provider, model, operation):
    from .model_policy import canonical
    model = canonical(provider, model, operation)
    row = await conn.fetchrow('''
        SELECT v.version, v.schema::text FROM model_capability_versions v
        JOIN approved_models a ON (a.provider,a.model_id,a.operation)=(v.provider,v.model_id,v.operation)
        WHERE v.provider=$1 AND v.model_id=$2 AND v.operation=$3 AND v.published
        ''', provider, model, operation)
    if not row:
        return None
    return {'version': str(row['version']), 'schema': json.loads(row['schema'])}


async def snapshot(conn, request):
    version = await published_version(conn, request.provider, request.model, request.operation)
    if version:
        validate_params(version['schema'], request.params)
    return version


async def flux_card(conn):
    """Intersect the adapter's single-image request with the current published rules."""
    from .tariff_admin import default_params
    params = default_params('clodex', 'images.generate')
    version = await published_version(conn, 'clodex', FLUX_MODEL, 'images.generate') if conn is not None else None
    if version:
        try:
            validate_params(version['schema'], params)
        except Rejected:
            return None
    return {'params': params, 'label': f"Количество изображений: {params['n']}"}


async def validate_pinned(conn, request):
    if request.model_version is None:
        return  # Existing quotes have no invented historical version.
    from .model_policy import canonical
    data = request.model_version
    if not isinstance(data, dict) or set(data) != {'version', 'schema'}:
        raise Rejected('Некорректная версия модели.')
    try:
        from uuid import UUID
        version = UUID(data['version'])
    except (ValueError, TypeError, AttributeError):
        raise Rejected('Некорректная версия модели.') from None
    saved = await conn.fetchval('''SELECT schema::text FROM model_capability_versions
        WHERE provider=$1 AND model_id=$2 AND operation=$3 AND version=$4''',
        request.provider, canonical(request.provider, request.model, request.operation), request.operation, version)
    if saved is None or json.loads(saved) != data['schema']:
        raise Rejected('Версия модели недоступна.')
    validate_params(data['schema'], request.params)


async def stage(policy, user, external, provider, model, operation, schema):
    from .model_policy import admitted, canonical
    validate_schema(schema)
    model = canonical(provider, model, operation)
    async with policy.app.pool.acquire() as conn, conn.transaction():
        await policy.app.pricing.admin(conn, user, external)
        await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)', POLICY_LOCK)
        if not await admitted(conn, provider, model, operation):
            raise Rejected('Модель не допущена.')
        version = uuid4()
        await conn.execute('''INSERT INTO model_capability_versions(provider,model_id,operation,version,schema)
                              VALUES($1,$2,$3,$4,$5::jsonb)''', provider, model, operation, version, json.dumps(schema))
        return version


async def publish(policy, user, external, provider, model, operation, version):
    from .model_policy import admitted, canonical
    model = canonical(provider, model, operation)
    async with policy.app.pool.acquire() as conn, conn.transaction():
        await policy.app.pricing.admin(conn, user, external)
        await conn.execute('SELECT pg_advisory_xact_lock($1::bigint)', POLICY_LOCK)
        if not await admitted(conn, provider, model, operation):
            raise Rejected('Модель не допущена.')
        raw = await conn.fetchval('''SELECT schema::text FROM model_capability_versions
            WHERE provider=$1 AND model_id=$2 AND operation=$3 AND version=$4 FOR UPDATE''',
            provider, model, operation, version)
        if raw is None:
            raise Rejected('Версия модели не найдена.')
        validate_schema(json.loads(raw))
        await conn.execute('''UPDATE model_capability_versions SET published=false
            WHERE provider=$1 AND model_id=$2 AND operation=$3 AND published''', provider, model, operation)
        await conn.execute('''UPDATE model_capability_versions SET published=true
            WHERE provider=$1 AND model_id=$2 AND operation=$3 AND version=$4''', provider, model, operation, version)
