CREATE FUNCTION verify_referral_reversal() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    recipient uuid;
    earned bigint;
    available bigint;
BEGIN
    SELECT r.referrer_id,r.amount INTO recipient,earned
    FROM referral_rewards r JOIN ledger c ON c.id=r.capture_id AND c.kind='task_capture'
    JOIN ledger f ON f.id=NEW.refund_id AND f.kind='task_refund'
        AND f.task_quote_id=c.task_quote_id AND f.user_id=c.user_id AND f.da=-c.dr
    WHERE r.capture_id=NEW.capture_id;
    IF NOT FOUND OR NEW.amount<>earned THEN
        RAISE EXCEPTION 'referral reversal requires its confirmed refund';
    END IF;
    PERFORM 1 FROM wallets WHERE user_id=recipient AND mode='live' FOR UPDATE;
    SELECT coalesce(sum(l.available),0)::bigint INTO available
    FROM wallet_funding_lots l WHERE l.user_id=recipient AND l.mode='live' AND l.origin='REFERRAL';
    IF NEW.debited<>least(earned,available) THEN
        RAISE EXCEPTION 'referral reversal does not match available referral funds';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER referral_reversal_guard BEFORE INSERT ON referral_reversals
    FOR EACH ROW EXECUTE FUNCTION verify_referral_reversal();

CREATE FUNCTION verify_referral_debt_repayment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    recipient uuid;
    earned bigint;
    debt bigint;
BEGIN
    SELECT r.referrer_id,r.amount INTO STRICT recipient,earned
    FROM referral_rewards r JOIN ledger l ON l.id=r.reward_ledger_id AND l.kind='referral_reward'
        AND l.user_id=r.referrer_id AND l.da=r.amount
    WHERE r.capture_id=NEW.capture_id;
    PERFORM 1 FROM wallets WHERE user_id=recipient AND mode='live' FOR UPDATE;
    SELECT (
        coalesce((SELECT sum(v.debt_added) FROM referral_reversals v
                  JOIN referral_rewards r USING(capture_id) WHERE r.referrer_id=recipient),0)
      - coalesce((SELECT sum(p.amount) FROM referral_debt_repayments p
                 JOIN referral_rewards r USING(capture_id) WHERE r.referrer_id=recipient),0)
    )::bigint INTO debt;
    IF NEW.amount<>least(earned,debt) OR EXISTS (
        SELECT 1 FROM referral_reversals WHERE capture_id=NEW.capture_id
    ) THEN RAISE EXCEPTION 'invalid referral debt repayment'; END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER referral_debt_repayment_guard BEFORE INSERT ON referral_debt_repayments
    FOR EACH ROW EXECUTE FUNCTION verify_referral_debt_repayment();
