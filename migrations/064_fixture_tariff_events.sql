CREATE TABLE fixture_tariff_events (
    version bigint PRIMARY KEY CHECK (version > expected_version),
    expected_version bigint NOT NULL CHECK (expected_version > 0),
    request_id uuid NOT NULL UNIQUE,
    actor_id uuid NOT NULL REFERENCES users(id),
    previous_amount integer NOT NULL,
    amount integer NOT NULL,
    rollback_of bigint UNIQUE REFERENCES fixture_tariff_events(version),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((previous_amount=2 AND amount=3 AND rollback_of IS NULL)
        OR (previous_amount=3 AND amount=2 AND rollback_of IS NOT NULL AND rollback_of=expected_version))
);

CREATE TRIGGER fixture_tariff_history_immutable
    BEFORE UPDATE OR DELETE ON fixture_tariff_events
    FOR EACH ROW EXECUTE FUNCTION immutable_row();

REVOKE ALL ON fixture_tariff_events FROM PUBLIC;
