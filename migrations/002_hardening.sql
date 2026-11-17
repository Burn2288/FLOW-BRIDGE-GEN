ALTER TABLE jobs ADD CONSTRAINT positive_cost CHECK(cost_bound>0);
CREATE FUNCTION insert_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.status<>'queued' OR NEW.settlement IS NOT NULL THEN RAISE EXCEPTION 'new jobs must be queued'; END IF;
 IF NOT EXISTS(SELECT 1 FROM quotes WHERE id=NEW.quote_id AND user_id=NEW.user_id AND mode=NEW.mode AND price=NEW.price AND cost_bound=NEW.cost_bound) THEN RAISE EXCEPTION 'quote job mismatch'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER new_job_guard BEFORE INSERT ON jobs FOR EACH ROW EXECUTE FUNCTION insert_job_guard();
CREATE FUNCTION check_job_ledger() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE j jobs; BEGIN
 SELECT * INTO j FROM jobs WHERE id=NEW.job_id;
 IF NEW.kind IN ('capture','release') AND j.settlement IS DISTINCT FROM NEW.kind THEN RAISE EXCEPTION 'settlement mismatch'; END IF;
 RETURN NULL; END $$;
CREATE CONSTRAINT TRIGGER matching_settlement AFTER INSERT ON ledger DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_job_ledger();
-- Inbox is private data; quarantined failures are never silently discarded.
ALTER TABLE inbox ADD COLUMN error_code text;
