-- Compose grants table DML and sequence access by default. Only the trusted
-- database writer may append role events or advance their audit sequence.
DO $$
BEGIN
    IF to_regrole('elevenbot_app') IS NOT NULL THEN
        REVOKE INSERT, DELETE ON http_admin_role_events FROM elevenbot_app;
        REVOKE ALL ON SEQUENCE http_admin_role_events_revision_seq FROM elevenbot_app;
    END IF;
END
$$;

-- UPDATE privilege is needed for LOCK TABLE ... IN SHARE MODE, used to
-- serialize protected actions with role revocation. The immutable row trigger
-- rejects updates to the history itself.
