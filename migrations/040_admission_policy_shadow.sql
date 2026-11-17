-- Additive, inert shadow state: no existing account is enrolled or revoked.
CREATE TABLE admission_policy_shadow (
    id smallint PRIMARY KEY CHECK (id = 1),
    version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
    initialized boolean NOT NULL DEFAULT false
);
INSERT INTO admission_policy_shadow(id) VALUES (1);

CREATE TABLE admission_membership_shadow (
    telegram_id bigint PRIMARY KEY CHECK (telegram_id > 0 AND telegram_id < 4503599627370496),
    role text NOT NULL CHECK (role IN ('admin','tester'))
);

CREATE TABLE admission_policy_audit_shadow (
    operation_id uuid PRIMARY KEY,
    actor_telegram_id bigint NOT NULL CHECK (actor_telegram_id > 0 AND actor_telegram_id < 4503599627370496),
    version bigint NOT NULL UNIQUE CHECK (version > 0),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION admission_shadow_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'admission shadow audit is immutable'; END $$;
CREATE TRIGGER admission_shadow_audit_no_update BEFORE UPDATE OR DELETE
    ON admission_policy_audit_shadow FOR EACH ROW EXECUTE FUNCTION admission_shadow_audit_immutable();
