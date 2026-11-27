-- Validate restoration obligations even when written outside the application.
CREATE FUNCTION verify_referral_restoration_repayment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    restored bigint;
    debt bigint;
    origin_id uuid;
BEGIN
    SELECT l.id INTO origin_id FROM ledger l
    WHERE l.id=NEW.restoration_id AND l.user_id=NEW.user_id AND l.mode='live' AND l.da>0
      AND l.kind IN ('release','task_release','task_refund','refund_release');
    IF NOT FOUND THEN RAISE EXCEPTION 'invalid referral restoration event'; END IF;
    PERFORM 1 FROM wallets WHERE user_id=NEW.user_id AND mode='live' FOR UPDATE;
    SELECT coalesce(sum(a.amount),0)::bigint INTO restored
    FROM wallet_funding_allocations a
    JOIN wallet_funding_lots f ON f.id=a.lot_id AND f.origin='REFERRAL'
       AND f.user_id=NEW.user_id AND f.mode='live'
    WHERE a.debit_ledger_id=(
        SELECT source.id FROM ledger event JOIN ledger source
            ON source.user_id=event.user_id AND source.mode=event.mode
        WHERE event.id=origin_id AND (
            (event.kind='release' AND source.kind='reserve' AND source.job_id=event.job_id)
            OR (event.kind IN ('task_release','task_refund') AND source.kind='task_reserve'
                AND source.task_quote_id=event.task_quote_id)
            OR (event.kind='refund_release' AND source.kind='refund_hold'
                AND source.payment_id=event.payment_id AND source.created_at<=event.created_at)
        )
        ORDER BY source.created_at DESC,source.id DESC LIMIT 1
    );
    SELECT coalesce((SELECT outstanding FROM referral_debt_balances WHERE user_id=NEW.user_id),0)
    INTO debt;
    IF NEW.amount<>least(restored,debt) THEN
        RAISE EXCEPTION 'restoration repayment exceeds or differs from proven referral amount';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER referral_restoration_repayment_guard BEFORE INSERT ON referral_restoration_repayments
    FOR EACH ROW EXECUTE FUNCTION verify_referral_restoration_repayment();

CREATE FUNCTION verify_restoration_repayment_ledger() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM ledger l WHERE l.id=NEW.ledger_id AND l.user_id=NEW.user_id
        AND l.mode='live' AND l.kind='referral_debt_repay' AND l.da=-NEW.amount AND l.dr=0
        AND l.event_key='referral-restoration-repay:'||NEW.restoration_id)
    THEN RAISE EXCEPTION 'restoration repayment missing its matching ledger debit'; END IF;
    RETURN NULL;
END
$$;
CREATE CONSTRAINT TRIGGER referral_restoration_repayment_ledger AFTER INSERT ON referral_restoration_repayments
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_restoration_repayment_ledger();
