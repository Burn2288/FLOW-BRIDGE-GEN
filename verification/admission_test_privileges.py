"""Disposable-test-only ACL setup; never run as production provisioning."""
import re

TABLES = ('admission_policy_shadow', 'admission_membership_shadow', 'admission_policy_audit_shadow')


def ident(value, prefix):
    if not re.fullmatch(prefix + r'[a-f0-9]{32}', value):
        raise ValueError('unsafe test identifier')
    return '"' + value + '"'


async def setup_test_acl(conn, schema, migration, runtime, policy):
    """Apply ACL only inside generated pytest schema to generated fixture roles."""
    s = ident(schema, 'test_')
    mig, run, pol = (ident(value, prefix) for value, prefix in
                     ((migration, 'tq_m_'), (runtime, 'tq_r_'), (policy, 'tq_p_')))
    if len({mig, run, pol}) != 3:
        raise ValueError('roles must differ')
    await conn.execute(f'REVOKE CREATE ON SCHEMA {s} FROM PUBLIC, {run}, {pol}')
    await conn.execute(f'GRANT USAGE, CREATE ON SCHEMA {s} TO {mig}')
    await conn.execute(f'GRANT USAGE ON SCHEMA {s} TO {run}, {pol}')
    for table in TABLES:
        name = f'{s}."{table}"'
        await conn.execute(f'ALTER TABLE {name} OWNER TO {mig}')
        await conn.execute(f'REVOKE ALL ON TABLE {name} FROM PUBLIC, {run}, {pol}')
        await conn.execute(f'GRANT SELECT ON TABLE {name} TO {run}, {pol}')
    await conn.execute(f'ALTER FUNCTION {s}.admission_shadow_audit_immutable() OWNER TO {mig}')
    await conn.execute(f'REVOKE ALL ON FUNCTION {s}.admission_shadow_audit_immutable() FROM PUBLIC, {run}, {pol}')
    await conn.execute(f'GRANT UPDATE ON {s}.admission_policy_shadow TO {pol}')
    await conn.execute(f'GRANT INSERT, DELETE ON {s}.admission_membership_shadow TO {pol}')
    await conn.execute(f'GRANT INSERT ON {s}.admission_policy_audit_shadow TO {pol}')
