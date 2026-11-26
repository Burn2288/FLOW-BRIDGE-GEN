ALTER TABLE approved_models ADD COLUMN visibility text NOT NULL DEFAULT 'VISIBLE'
    CHECK (visibility IN ('VISIBLE', 'HIDDEN'));
ALTER TABLE approved_models ADD COLUMN visibility_version bigint NOT NULL DEFAULT 0
    CHECK (visibility_version >= 0);

CREATE TABLE model_visibility_events (
    version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id uuid NOT NULL UNIQUE,
    actor_id uuid NOT NULL REFERENCES users(id),
    provider text NOT NULL,
    model_id text NOT NULL,
    operation text NOT NULL,
    expected_version bigint NOT NULL,
    previous_visibility text NOT NULL CHECK (previous_visibility IN ('VISIBLE', 'HIDDEN')),
    visibility text NOT NULL CHECK (visibility IN ('VISIBLE', 'HIDDEN')),
    rollback_of bigint REFERENCES model_visibility_events(version),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CHECK (visibility <> previous_visibility)
);

CREATE TRIGGER model_visibility_history_immutable
    BEFORE UPDATE OR DELETE ON model_visibility_events
    FOR EACH ROW EXECUTE FUNCTION immutable_row();
REVOKE ALL ON model_visibility_events FROM PUBLIC;

CREATE INDEX model_visibility_latest ON model_visibility_events(provider, model_id, operation, version DESC);

-- Preserve the approved visibility decision if the same model is re-admitted.
CREATE FUNCTION restore_model_visibility_on_admission() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    latest model_visibility_events%ROWTYPE;
BEGIN
    SELECT * INTO latest FROM model_visibility_events
    WHERE (provider, model_id, operation) = (NEW.provider, NEW.model_id, NEW.operation)
    ORDER BY version DESC LIMIT 1;
    IF FOUND THEN
        NEW.visibility := latest.visibility;
        NEW.visibility_version := latest.version;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER model_visibility_restore_on_admission BEFORE INSERT ON approved_models
    FOR EACH ROW EXECUTE FUNCTION restore_model_visibility_on_admission();
