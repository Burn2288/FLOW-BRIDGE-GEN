CREATE FUNCTION preserve_job_contract() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.user_id,NEW.mode,NEW.quote_id,NEW.price,NEW.cost_bound,NEW.budget_day) IS DISTINCT FROM
    (OLD.user_id,OLD.mode,OLD.quote_id,OLD.price,OLD.cost_bound,OLD.budget_day) THEN RAISE EXCEPTION 'job contract immutable'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER preserve_job BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION preserve_job_contract();
CREATE FUNCTION require_reserve() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM ledger WHERE job_id=NEW.id AND kind='reserve') THEN RAISE EXCEPTION 'job reserve missing'; END IF;
 RETURN NULL; END $$;
CREATE CONSTRAINT TRIGGER job_has_reserve AFTER INSERT ON jobs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_reserve();
CREATE FUNCTION preserve_payment_contract() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF (NEW.user_id,NEW.amount,NEW.credits,NEW.currency,NEW.tariff) IS DISTINCT FROM
    (OLD.user_id,OLD.amount,OLD.credits,OLD.currency,OLD.tariff) THEN RAISE EXCEPTION 'payment contract immutable'; END IF;
 IF OLD.charge_id IS NOT NULL AND NEW.charge_id IS DISTINCT FROM OLD.charge_id THEN RAISE EXCEPTION 'charge immutable'; END IF;
 IF OLD.status='refunded' AND NEW.status<>OLD.status THEN RAISE EXCEPTION 'refunded payment immutable'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER preserve_payment BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION preserve_payment_contract();
