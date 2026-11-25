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
