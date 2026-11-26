ALTER TABLE http_admin_role_events ADD COLUMN previous_role text
    CHECK(previous_role IN ('OWNER_ADMIN','READ_ONLY_ADMIN','SUPPORT_OPERATOR','SETTINGS_OPERATOR'));
ALTER TABLE http_admin_role_events ADD COLUMN operation_id uuid UNIQUE;

-- Invoke as the migration owner or an explicitly delegated database principal.
-- No default delegation and no application HTTP writer.
CREATE FUNCTION change_http_admin_role(
    target uuid, actor uuid, desired_role text, expected_revision bigint,
    event_id uuid, audit_reason text
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    current_event http_admin_role_events%ROWTYPE;
    prior_event http_admin_role_events%ROWTYPE;
    next_revision bigint;
BEGIN
    IF target IS NULL OR actor IS NULL OR target=actor OR expected_revision IS NULL OR event_id IS NULL
       OR audit_reason IS NULL OR char_length(trim(audit_reason)) NOT BETWEEN 1 AND 200
       OR (desired_role IS NOT NULL AND desired_role NOT IN ('READ_ONLY_ADMIN','SUPPORT_OPERATOR','SETTINGS_OPERATOR'))
    THEN RAISE EXCEPTION 'invalid admin role change'; END IF;
    LOCK TABLE http_admin_role_events IN SHARE ROW EXCLUSIVE MODE;
    IF (SELECT role FROM http_admin_role_events WHERE subject_id=actor ORDER BY revision DESC LIMIT 1)
       IS DISTINCT FROM 'OWNER_ADMIN'
       OR NOT EXISTS (SELECT 1 FROM users WHERE id=actor AND NOT blocked)
    THEN RAISE EXCEPTION 'owner authority required'; END IF;
    IF NOT EXISTS (SELECT 1 FROM users WHERE id=target AND NOT blocked)
    THEN RAISE EXCEPTION 'target identity missing or blocked'; END IF;
    SELECT * INTO prior_event FROM http_admin_role_events WHERE operation_id=event_id;
    IF FOUND THEN
        IF (prior_event.subject_id,prior_event.actor_id,prior_event.role,prior_event.reason)
           IS DISTINCT FROM (target,actor,desired_role,audit_reason)
        THEN RAISE EXCEPTION 'admin event identity conflict'; END IF;
        RETURN prior_event.revision;
    END IF;
    SELECT * INTO current_event FROM http_admin_role_events
    WHERE subject_id=target ORDER BY revision DESC LIMIT 1;
    IF coalesce(current_event.revision,0)<>expected_revision
       OR current_event.role IS NOT DISTINCT FROM 'OWNER_ADMIN'
       OR current_event.role IS NOT DISTINCT FROM desired_role
    THEN RAISE EXCEPTION 'stale or prohibited admin role change'; END IF;
    INSERT INTO http_admin_role_events(subject_id,actor_id,role,reason,previous_role,operation_id)
    VALUES(target,actor,desired_role,audit_reason,current_event.role,event_id)
    RETURNING revision INTO next_revision;
    RETURN next_revision;
END
$$;
REVOKE ALL ON FUNCTION change_http_admin_role(uuid,uuid,text,bigint,uuid,text) FROM PUBLIC;
