"""Inert shadow primitives; NOT wired to runtime authorization or admin APIs.

Caller is responsible for verified identity and independent admin authorization.
Never use these primitives as production authorization without a separately
reviewed role boundary, complete route integration and explicit cutover.
"""
from dataclasses import dataclass
import hashlib
import json
import logging
from uuid import UUID

from .admission import admitted


class PolicyUnavailable(Exception):
    pass


class PolicyDenied(Exception):
    pass


class VersionConflict(Exception):
    pass


class CutoverBlocked(Exception):
    pass


@dataclass(frozen=True)
class Decision:
    version: int
    allowed: bool
    role: str | None


def _identity(value):
    if type(value) is not int or not 0 < value < 2**52:
        raise ValueError('invalid subject')
    return value


def _payload(admins, testers):
    admins, testers = set(admins), set(testers)
    if not admins or admins & testers:
        raise ValueError('invalid membership')
    for user in admins | testers:
        _identity(user)
    canonical = json.dumps({'admins': sorted(admins), 'testers': sorted(testers)},
                           sort_keys=True, separators=(',', ':')).encode()
    return admins, testers, hashlib.sha256(canonical).hexdigest()


async def replace_policy(pool, *, expected_version, operation_id, actor, admins, testers,
                         authorize_admin):
    """Internal candidate API; external callers must never choose the authorizer.

    Authorization is deliberately injected for isolated tests. Production DB
    privileges and non-forgeable admin authentication are unresolved blockers.
    """
    actor = _identity(actor)
    if type(expected_version) is not int or expected_version < 0 or not isinstance(operation_id, UUID):
        raise ValueError('invalid update metadata')
    admins, testers, digest = _payload(admins, testers)
    async with pool.acquire() as conn, conn.transaction():
        if authorize_admin is None or not await authorize_admin(conn, actor):
            raise PolicyDenied('admin authorization required')
        state = await conn.fetchrow('SELECT version FROM admission_policy_shadow WHERE id=1 FOR UPDATE')
        if state is None:
            raise PolicyUnavailable('policy unavailable')
        previous = await conn.fetchrow('SELECT version,payload_sha256,actor_telegram_id FROM admission_policy_audit_shadow WHERE operation_id=$1', operation_id)
        if previous:
            if previous['payload_sha256'] != digest or previous['actor_telegram_id'] != actor:
                raise VersionConflict('operation mismatch')
            return previous['version']
        if state['version'] != expected_version:
            raise VersionConflict('policy version mismatch')
        await conn.execute('DELETE FROM admission_membership_shadow')
        await conn.executemany('INSERT INTO admission_membership_shadow(telegram_id,role) VALUES($1,$2)',
                               [(v, 'admin') for v in sorted(admins)] + [(v, 'tester') for v in sorted(testers)])
        version = state['version'] + 1
        await conn.execute('UPDATE admission_policy_shadow SET version=$1,initialized=true WHERE id=1', version)
        await conn.execute('INSERT INTO admission_policy_audit_shadow(operation_id,actor_telegram_id,version,payload_sha256) VALUES($1,$2,$3,$4)', operation_id, actor, version, digest)
        return version


async def decide_on(conn, telegram_id):
    """Caller supplies a verified Telegram ID; policy lock lasts caller transaction."""
    _identity(telegram_id)
    if not conn.is_in_transaction():
        raise ValueError('transaction required')
    sql = 'SELECT version,initialized FROM admission_policy_shadow WHERE id=1 FOR SHARE'
    state = await conn.fetchrow(sql)
    if state is None or not state['initialized']:
        raise PolicyUnavailable('policy unavailable')
    role = await conn.fetchval('SELECT role FROM admission_membership_shadow WHERE telegram_id=$1', telegram_id)
    return Decision(state['version'], role is not None, role)


async def require_on(conn, telegram_id):
    decision = await decide_on(conn, telegram_id)
    if not decision.allowed:
        raise PolicyDenied('access denied')
    return decision


async def shadow_compare(pool, config, telegram_id):
    """Return legacy decision and mismatch category; never enables DB policy."""
    legacy = admitted(config, telegram_id)
    try:
        async with pool.acquire() as conn, conn.transaction():
            shadow = await decide_on(conn, telegram_id)
    except Exception:
        logging.getLogger(__name__).info('admission_shadow comparison=SHADOW_UNAVAILABLE')
        return legacy, 'SHADOW_UNAVAILABLE'
    category = 'MATCH' if legacy == shadow.allowed else 'MISMATCH'
    logging.getLogger(__name__).info('admission_shadow comparison=%s', category)
    return legacy, category


def enable_authoritative_policy():
    raise CutoverBlocked('authoritative cutover and rollback are not implemented')
