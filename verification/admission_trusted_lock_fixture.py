"""Disposable-only SECURITY DEFINER prototype; NOT deployment provisioning."""
from verification.admission_test_privileges import ident


async def install(conn, schema, owner, runtime):
    s = ident(schema, 'test_')
    o = ident(owner, 'tq_f_')
    r = ident(runtime, 'tq_r_')
    await conn.execute(f'GRANT USAGE, CREATE ON SCHEMA {s} TO {o}')
    await conn.execute(f'GRANT SELECT, UPDATE ON {s}.admission_policy_shadow TO {o}')
    await conn.execute(f'GRANT SELECT ON {s}.admission_membership_shadow TO {o}')
    # Only fixture-generated identifiers are interpolated, never a request value.
    await conn.execute(f'''CREATE FUNCTION {s}.fixture_admission_lock(subject pg_catalog.int8)
      RETURNS TABLE(policy_version pg_catalog.int8, admitted pg_catalog.bool, member_role pg_catalog.text)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
      DECLARE revision pg_catalog.int8; ready pg_catalog.bool;
      BEGIN
        IF subject IS NULL OR subject <= 0 OR subject >= 4503599627370496 THEN
          RAISE EXCEPTION USING ERRCODE='P0001', MESSAGE='invalid subject';
        END IF;
        SELECT p.version,p.initialized INTO revision,ready
          FROM {s}.admission_policy_shadow AS p WHERE p.id=1 FOR SHARE;
        IF NOT FOUND OR NOT ready THEN
          RAISE EXCEPTION USING ERRCODE='P0001', MESSAGE='policy unavailable';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM {s}.admission_membership_shadow AS a WHERE a.role='admin') THEN
          RAISE EXCEPTION USING ERRCODE='P0001', MESSAGE='policy incomplete';
        END IF;
        RETURN QUERY SELECT revision, m.role IS NOT NULL, m.role
          FROM (SELECT 1) AS one LEFT JOIN {s}.admission_membership_shadow AS m
          ON m.telegram_id=subject;
      END $$''')
    await conn.execute(f'ALTER FUNCTION {s}.fixture_admission_lock(pg_catalog.int8) OWNER TO {o}')
    await conn.execute(f'''CREATE FUNCTION {s}.fixture_membership_write_lock()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
      BEGIN
        PERFORM 1 FROM {s}.admission_policy_shadow AS p WHERE p.id=1 FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION USING ERRCODE='P0001', MESSAGE='policy unavailable';
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
      END $$''')
    await conn.execute(f'ALTER FUNCTION {s}.fixture_membership_write_lock() OWNER TO {o}')
    await conn.execute(f'REVOKE ALL ON FUNCTION {s}.fixture_membership_write_lock() FROM PUBLIC')
    await conn.execute(f'''CREATE TRIGGER fixture_membership_write_lock
      BEFORE INSERT OR UPDATE OR DELETE ON {s}.admission_membership_shadow
      FOR EACH ROW EXECUTE FUNCTION {s}.fixture_membership_write_lock()''')
    await conn.execute(f'REVOKE CREATE ON SCHEMA {s} FROM {o}')
    await conn.execute(f'REVOKE ALL ON FUNCTION {s}.fixture_admission_lock(pg_catalog.int8) FROM PUBLIC')
    await conn.execute(f'GRANT EXECUTE ON FUNCTION {s}.fixture_admission_lock(pg_catalog.int8) TO {r}')
