-- Track the provenance of ledger movements without changing wallet balances.
CREATE TABLE wallet_funding_lots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL,
    mode text NOT NULL,
    origin text NOT NULL CHECK (origin IN ('PROMOTIONAL','REFERRAL','PAID','UNKNOWN_LEGACY')),
    credit_ledger_id uuid UNIQUE REFERENCES ledger(id),
    payment_id uuid REFERENCES payments(id),
    available bigint NOT NULL CHECK (available >= 0),
    FOREIGN KEY (user_id,mode) REFERENCES wallets(user_id,mode),
    CHECK ((origin='PAID') = (payment_id IS NOT NULL)),
    CHECK (origin<>'PAID' OR credit_ledger_id IS NOT NULL)
);
CREATE INDEX wallet_funding_spend ON wallet_funding_lots(user_id,mode,id)
    WHERE available>0;
CREATE TABLE wallet_funding_allocations (
    debit_ledger_id uuid NOT NULL REFERENCES ledger(id),
    lot_id bigint NOT NULL REFERENCES wallet_funding_lots(id),
    amount bigint NOT NULL CHECK (amount>0),
    PRIMARY KEY (debit_ledger_id,lot_id)
);
CREATE TRIGGER wallet_funding_allocations_immutable
    BEFORE UPDATE OR DELETE ON wallet_funding_allocations
    FOR EACH ROW EXECUTE FUNCTION immutable_row();

-- Establish the baseline while excluding concurrent ledger writes.
LOCK TABLE ledger IN SHARE ROW EXCLUSIVE MODE;
INSERT INTO wallet_funding_lots(user_id,mode,origin,available)
SELECT user_id,mode,'UNKNOWN_LEGACY',available FROM wallets WHERE available>0;

CREATE FUNCTION track_wallet_funding() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    source_debit uuid;
    item record;
    remaining bigint := abs(NEW.da);
    portion bigint;
    category text;
BEGIN
    -- The earlier movement trigger holds the wallet row lock until commit.
    IF NEW.da<0 THEN
        FOR item IN SELECT id,available FROM wallet_funding_lots
            WHERE user_id=NEW.user_id AND mode=NEW.mode AND available>0
            ORDER BY CASE origin WHEN 'PROMOTIONAL' THEN 1 WHEN 'REFERRAL' THEN 2
                WHEN 'PAID' THEN 3 ELSE 4 END,id
            FOR UPDATE
        LOOP
            portion := least(item.available,remaining);
            UPDATE wallet_funding_lots SET available=available-portion WHERE id=item.id;
            INSERT INTO wallet_funding_allocations VALUES(NEW.id,item.id,portion);
            remaining := remaining-portion;
            EXIT WHEN remaining=0;
        END LOOP;
        IF remaining<>0 THEN RAISE EXCEPTION 'wallet funding allocation mismatch'; END IF;
    ELSIF NEW.da>0 THEN
        SELECT id INTO source_debit FROM ledger
        WHERE user_id=NEW.user_id AND mode=NEW.mode AND (
            (NEW.kind IN ('task_release','task_refund') AND kind='task_reserve' AND task_quote_id=NEW.task_quote_id)
            OR (NEW.kind='release' AND kind='reserve' AND job_id=NEW.job_id)
            OR (NEW.kind='refund_release' AND kind='refund_hold' AND payment_id=NEW.payment_id)
        )
        ORDER BY created_at DESC,id DESC LIMIT 1;
        IF source_debit IS NOT NULL THEN
            FOR item IN SELECT lot_id,amount FROM wallet_funding_allocations
                WHERE debit_ledger_id=source_debit ORDER BY lot_id
            LOOP
                UPDATE wallet_funding_lots SET available=available+item.amount WHERE id=item.lot_id;
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
            INSERT INTO wallet_funding_lots(user_id,mode,origin,credit_ledger_id,payment_id,available)
            VALUES(NEW.user_id,NEW.mode,category,NEW.id,
                CASE WHEN category='PAID' THEN NEW.payment_id END,remaining);
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER zz_wallet_funding AFTER INSERT ON ledger
    FOR EACH ROW EXECUTE FUNCTION track_wallet_funding();
