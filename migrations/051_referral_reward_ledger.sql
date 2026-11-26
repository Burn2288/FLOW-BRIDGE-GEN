CREATE TABLE referral_rewards (
    capture_id uuid PRIMARY KEY REFERENCES ledger(id),
    reserve_id uuid NOT NULL UNIQUE REFERENCES referral_policy_snapshots(reserve_ledger_id),
    referrer_id uuid NOT NULL REFERENCES users(id),
    eligible_paid bigint NOT NULL CHECK (eligible_paid>0),
    amount bigint NOT NULL CHECK (amount>0),
    reward_ledger_id uuid NOT NULL UNIQUE REFERENCES ledger(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER referral_reward_immutable BEFORE UPDATE OR DELETE ON referral_rewards
    FOR EACH ROW EXECUTE FUNCTION immutable_row();

CREATE FUNCTION verify_referral_reward_ledger() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM referral_rewards r WHERE r.reward_ledger_id=NEW.id
        AND r.referrer_id=NEW.user_id AND r.amount=NEW.da
        AND NEW.event_key='referral-reward:'||r.capture_id)
    THEN RAISE EXCEPTION 'referral reward origin missing'; END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER referral_reward_origin BEFORE INSERT ON ledger
    FOR EACH ROW WHEN (NEW.kind='referral_reward') EXECUTE FUNCTION verify_referral_reward_ledger();

-- Keep the existing checks for every pre-existing kind.
DO $install$
DECLARE
    definition text;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO STRICT definition FROM pg_constraint
    WHERE conrelid='ledger'::regclass AND conname='ledger_kind_check';
    EXECUTE 'ALTER TABLE ledger DROP CONSTRAINT ledger_kind_check';
    EXECUTE 'ALTER TABLE ledger ADD CONSTRAINT ledger_kind_check CHECK (kind=''referral_reward'' OR ' ||
        substring(definition FROM 7) || ')';
    SELECT pg_get_constraintdef(oid) INTO STRICT definition FROM pg_constraint
    WHERE conrelid='ledger'::regclass AND conname='ledger_movement_shape';
    EXECUTE 'ALTER TABLE ledger DROP CONSTRAINT ledger_movement_shape';
    EXECUTE 'ALTER TABLE ledger ADD CONSTRAINT ledger_movement_shape CHECK (' ||
        '(kind=''referral_reward'' AND mode=''live'' AND da>0 AND dr=0 ' ||
        'AND job_id IS NULL AND payment_id IS NULL AND task_quote_id IS NULL) OR ' ||
        substring(definition FROM 7) || ')';
END
$install$;

-- The shared funding trigger creates the lot first in the same transaction.
CREATE FUNCTION classify_referral_reward_lot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE wallet_funding_lots SET origin='REFERRAL' WHERE credit_ledger_id=NEW.id;
    IF NOT FOUND THEN RAISE EXCEPTION 'referral reward funding lot missing'; END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER zzz_classify_referral_reward_lot AFTER INSERT ON ledger
    FOR EACH ROW WHEN (NEW.kind='referral_reward') EXECUTE FUNCTION classify_referral_reward_lot();
