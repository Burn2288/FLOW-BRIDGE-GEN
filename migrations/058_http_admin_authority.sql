CREATE TABLE http_admin_role_events (
    revision bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id uuid NOT NULL REFERENCES users(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    role text CHECK(role IN ('OWNER_ADMIN','READ_ONLY_ADMIN','SUPPORT_OPERATOR','SETTINGS_OPERATOR')),
    reason text NOT NULL CHECK(char_length(trim(reason)) BETWEEN 1 AND 200),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX http_admin_role_latest ON http_admin_role_events(subject_id,revision DESC);
CREATE TRIGGER http_admin_role_history_immutable BEFORE UPDATE OR DELETE ON http_admin_role_events
    FOR EACH ROW EXECUTE FUNCTION immutable_row();
REVOKE ALL ON http_admin_role_events FROM PUBLIC;
