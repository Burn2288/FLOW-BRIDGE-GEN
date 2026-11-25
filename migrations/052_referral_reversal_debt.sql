CREATE TABLE referral_reversals (
    capture_id uuid PRIMARY KEY REFERENCES referral_rewards(capture_id),
    refund_id uuid NOT NULL UNIQUE REFERENCES ledger(id),
    amount bigint NOT NULL CHECK (amount>0),
    debited bigint NOT NULL CHECK (debited>=0),
    debt_added bigint NOT NULL CHECK (debt_added>=0),
    ledger_id uuid UNIQUE REFERENCES ledger(id) DEFERRABLE INITIALLY DEFERRED,
    CHECK (amount=debited+debt_added),
    CHECK ((debited>0)=(ledger_id IS NOT NULL))
);
CREATE TABLE referral_debt_repayments (
    capture_id uuid PRIMARY KEY REFERENCES referral_rewards(capture_id),
    amount bigint NOT NULL CHECK (amount>0),
    ledger_id uuid NOT NULL UNIQUE REFERENCES ledger(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER referral_reversal_immutable BEFORE UPDATE OR DELETE ON referral_reversals
    FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER referral_debt_repayment_immutable BEFORE UPDATE OR DELETE ON referral_debt_repayments
    FOR EACH ROW EXECUTE FUNCTION immutable_row();

DO $install$
DECLARE
    definition text;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO STRICT definition FROM pg_constraint
    WHERE conrelid='ledger'::regclass AND conname='ledger_kind_check';
    EXECUTE 'ALTER TABLE ledger DROP CONSTRAINT ledger_kind_check';
    EXECUTE 'ALTER TABLE ledger ADD CONSTRAINT ledger_kind_check CHECK (kind IN '
        || '(''referral_reversal'',''referral_debt_repay'') OR ' || substring(definition FROM 7) || ')';
    SELECT pg_get_constraintdef(oid) INTO STRICT definition FROM pg_constraint
    WHERE conrelid='ledger'::regclass AND conname='ledger_movement_shape';
    EXECUTE 'ALTER TABLE ledger DROP CONSTRAINT ledger_movement_shape';
    EXECUTE 'ALTER TABLE ledger ADD CONSTRAINT ledger_movement_shape CHECK ('
        || '(kind IN (''referral_reversal'',''referral_debt_repay'') AND mode=''live'' AND da<0 AND dr=0 '
        || 'AND job_id IS NULL AND payment_id IS NULL AND task_quote_id IS NULL) OR '
        || substring(definition FROM 7) || ')';
END
$install$;

CREATE FUNCTION verify_referral_debit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind='referral_reversal' AND EXISTS (
        SELECT 1 FROM referral_reversals v JOIN referral_rewards r USING(capture_id)
        JOIN ledger f ON f.id=v.refund_id JOIN ledger c ON c.id=r.capture_id
        WHERE v.ledger_id=NEW.id AND r.referrer_id=NEW.user_id AND v.debited=-NEW.da
          AND v.amount=r.amount AND f.kind='task_refund' AND c.kind='task_capture'
          AND f.task_quote_id=c.task_quote_id AND f.user_id=c.user_id
          AND NEW.event_key='referral-reversal:'||v.capture_id
    ) THEN RETURN NEW; END IF;
    IF NEW.kind='referral_debt_repay' AND EXISTS (
        SELECT 1 FROM referral_debt_repayments p JOIN referral_rewards r USING(capture_id)
        WHERE p.ledger_id=NEW.id AND r.referrer_id=NEW.user_id AND p.amount=-NEW.da
          AND p.amount<=r.amount AND NEW.event_key='referral-debt-repay:'||p.capture_id
    ) THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'referral debit origin missing';
END
$$;
CREATE TRIGGER referral_debit_origin BEFORE INSERT ON ledger FOR EACH ROW
    WHEN (NEW.kind IN ('referral_reversal','referral_debt_repay')) EXECUTE FUNCTION verify_referral_debit();

-- Keep migration 048 checksums intact. Ledger writers may invoke the existing
-- trigger, but cannot update provenance tables directly.
DO $install$
DECLARE
    target_schema text := current_schema();
BEGIN
    EXECUTE replace($definition$
CREATE OR REPLACE FUNCTION @schema@.track_wallet_funding() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    source_debit uuid;
    item record;
    remaining bigint := abs(NEW.da);
    portion bigint;
    category text;
BEGIN
    IF TG_RELID <> '@schema@.ledger'::regclass OR TG_OP <> 'INSERT'
       OR TG_WHEN <> 'AFTER' OR TG_LEVEL <> 'ROW' THEN
        RAISE EXCEPTION 'funding tracker requires its ledger trigger';
    END IF;
    -- The earlier movement trigger holds the wallet row lock until commit.
    IF NEW.da<0 THEN
        FOR item IN SELECT id,available FROM @schema@.wallet_funding_lots
            WHERE user_id=NEW.user_id AND mode=NEW.mode AND available>0
              AND (NEW.kind NOT IN ('referral_reversal','referral_debt_repay') OR origin='REFERRAL')
            ORDER BY CASE WHEN NEW.kind IN ('refund_hold','topup_reversal','topup_debt_repay')
                          AND payment_id=NEW.payment_id THEN 0 ELSE 1 END,
                     CASE WHEN NEW.kind IN ('refund_hold','topup_reversal','topup_debt_repay')
                          AND origin='UNKNOWN_LEGACY' THEN 0 ELSE 1 END,
                     CASE origin WHEN 'PROMOTIONAL' THEN 1 WHEN 'REFERRAL' THEN 2
                WHEN 'PAID' THEN 3 ELSE 4 END,id
            FOR UPDATE
        LOOP
            portion := least(item.available,remaining);
            UPDATE @schema@.wallet_funding_lots SET available=available-portion WHERE id=item.id;
            INSERT INTO @schema@.wallet_funding_allocations VALUES(NEW.id,item.id,portion);
            remaining := remaining-portion;
            EXIT WHEN remaining=0;
        END LOOP;
        IF remaining<>0 THEN RAISE EXCEPTION 'wallet funding allocation mismatch'; END IF;
    ELSIF NEW.da>0 THEN
        SELECT id INTO source_debit FROM @schema@.ledger
        WHERE user_id=NEW.user_id AND mode=NEW.mode AND (
            (NEW.kind IN ('task_release','task_refund') AND kind='task_reserve' AND task_quote_id=NEW.task_quote_id)
            OR (NEW.kind='release' AND kind='reserve' AND job_id=NEW.job_id)
            OR (NEW.kind='refund_release' AND kind='refund_hold' AND payment_id=NEW.payment_id)
        )
        ORDER BY created_at DESC,id DESC LIMIT 1;
        IF source_debit IS NOT NULL THEN
            FOR item IN SELECT lot_id,amount FROM @schema@.wallet_funding_allocations
                WHERE debit_ledger_id=source_debit ORDER BY lot_id
            LOOP
                UPDATE @schema@.wallet_funding_lots SET available=available+item.amount WHERE id=item.lot_id;
                remaining := remaining-item.amount;
            END LOOP;
        END IF;
        IF remaining<0 THEN RAISE EXCEPTION 'wallet funding restoration exceeds credit'; END IF;
        IF remaining>0 THEN
            category := CASE
                WHEN NEW.kind IN ('payment','topup') AND NEW.payment_id IS NOT NULL THEN 'PAID'
                WHEN NEW.kind IN ('demo_grant','pilot_grant') THEN 'PROMOTIONAL'
                ELSE 'UNKNOWN_LEGACY'
            END;
            INSERT INTO @schema@.wallet_funding_lots(user_id,mode,origin,credit_ledger_id,payment_id,available)
            VALUES(NEW.user_id,NEW.mode,category,NEW.id,
                CASE WHEN category='PAID' THEN NEW.payment_id END,remaining);
        END IF;
    END IF;
    RETURN NEW;
END $$;
$definition$, '@schema@', quote_ident(target_schema));
    EXECUTE format('REVOKE ALL ON FUNCTION %I.track_wallet_funding() FROM PUBLIC', target_schema);
END
$install$;
