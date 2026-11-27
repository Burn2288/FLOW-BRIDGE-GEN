"""One typed catalogue setting, shared by both administrative clients."""

from uuid import UUID

from .admin_authority import current_capabilities, has_capability


class VisibilityDenied(Exception):
    pass


class MissingModel(Exception):
    pass


class VisibilityConflict(Exception):
    pass


CAPABILITY = 'settings.visibility'
VISIBILITIES = {'VISIBLE', 'HIDDEN'}
FIELDS = """
    m.provider, m.model_id, m.operation, m.title, m.visibility,
    m.visibility_version AS version, e.previous_visibility
"""
MODELS = """
    FROM approved_models m
    LEFT JOIN model_visibility_events e ON e.version=m.visibility_version
"""


async def authorize(conn, actor):
    if not has_capability(await current_capabilities(conn, actor), CAPABILITY):
        raise VisibilityDenied()


async def list_models(conn, actor):
    await authorize(conn, actor)
    rows = await conn.fetch(f'SELECT {FIELDS} {MODELS} ORDER BY m.provider, m.title, m.model_id, m.operation')
    return [dict(row) for row in rows]


async def _model(conn, provider, model, operation, *, for_update=False):
    if any(not isinstance(value, str) or not 1 <= len(value) <= 256 or '\0' in value
           for value in (provider, model, operation)):
        raise ValueError('Invalid model key')
    if for_update and not await conn.fetchval('''
        SELECT 1 FROM approved_models WHERE (provider,model_id,operation)=($1,$2,$3) FOR UPDATE
    ''', provider, model, operation):
        raise MissingModel()
    row = await conn.fetchrow(f'''
        SELECT {FIELDS} {MODELS}
        WHERE (m.provider,m.model_id,m.operation)=($1,$2,$3)
    ''', provider, model, operation)
    if row is None:
        raise MissingModel()
    return dict(row)


def _validate_change(current, visibility, rollback_of):
    if visibility == current['visibility']:
        raise VisibilityConflict()
    if rollback_of is not None and (
        rollback_of != current['version'] or visibility != current['previous_visibility']
    ):
        raise VisibilityConflict()


def _typed(visibility, rollback_of):
    if not isinstance(visibility, str) or visibility not in VISIBILITIES:
        raise ValueError('Invalid model visibility')
    if rollback_of is not None and (type(rollback_of) is not int or not 0 < rollback_of < 2**63):
        raise ValueError('Invalid rollback version')


async def preview(conn, actor, provider, model, operation, visibility, rollback_of=None):
    await authorize(conn, actor)
    _typed(visibility, rollback_of)
    row = await _model(conn, provider, model, operation)
    _validate_change(row, visibility, rollback_of)
    return {**row, 'desired_visibility': visibility, 'rollback_of': rollback_of}


async def confirm(conn, actor, provider, model, operation, visibility, expected_version, request_id,
                  rollback_of=None):
    """Confirm in the caller's read-committed transaction."""
    if not conn.is_in_transaction():
        raise RuntimeError('Visibility confirmation requires a transaction')
    # Role writers use a conflicting table lock. Also serialize with user blocking.
    await conn.execute('LOCK TABLE http_admin_role_events IN SHARE MODE')
    await conn.fetchval('SELECT 1 FROM users WHERE id=$1 FOR SHARE', actor)
    await authorize(conn, actor)
    _typed(visibility, rollback_of)
    if type(expected_version) is not int or not 0 <= expected_version < 2**63 or not isinstance(request_id, UUID):
        raise ValueError('Invalid visibility confirmation')

    row = await _model(conn, provider, model, operation, for_update=True)
    fields = (actor, provider, model, operation, expected_version, visibility, rollback_of)
    replay = await conn.fetchrow('''
        SELECT actor_id, provider, model_id, operation, expected_version, visibility, rollback_of,
               version, previous_visibility
        FROM model_visibility_events WHERE request_id=$1
    ''', request_id)
    if replay is not None:
        return _replay(row, replay, fields)

    if row['version'] != expected_version:
        raise VisibilityConflict()
    _validate_change(row, visibility, rollback_of)
    version = await conn.fetchval('''
        INSERT INTO model_visibility_events(
            request_id, actor_id, provider, model_id, operation, expected_version,
            visibility, rollback_of, previous_visibility)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (request_id) DO NOTHING RETURNING version
    ''', request_id, *fields, row['visibility'])
    if version is None:
        # The same request ID was committed concurrently for a different model.
        raise VisibilityConflict()
    await conn.execute('''
        UPDATE approved_models SET visibility=$4, visibility_version=$5
        WHERE (provider,model_id,operation)=($1,$2,$3)
    ''', provider, model, operation, visibility, version)
    return {**row, 'visibility': visibility, 'version': version, 'previous_visibility': row['visibility']}


def _replay(row, event, fields):
    if tuple(event)[:len(fields)] != fields:
        raise VisibilityConflict()
    return {**row, 'visibility': event['visibility'], 'version': event['version'],
            'previous_visibility': event['previous_visibility']}
