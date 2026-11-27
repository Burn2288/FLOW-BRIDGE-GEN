-- D-07 / C-011 v1 ADDENDUM-01. An existing referral obligation survives
-- deactivation of new FUNCTIONAL_TEST rewards.
CREATE TABLE referral_restoration_repayments (
    restoration_id uuid PRIMARY KEY REFERENCES ledger(id),
    user_id uuid NOT NULL REFERENCES users(id),
    amount bigint NOT NULL CHECK (amount>0),
    ledger_id uuid NOT NULL UNIQUE REFERENCES ledger(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER referral_restoration_repayment_immutable
    BEFORE UPDATE OR DELETE ON referral_restoration_repayments
    FOR EACH ROW EXECUTE FUNCTION immutable_row();

CREATE VIEW referral_debt_balances AS
WITH movements AS (
    SELECT r.referrer_id AS user_id,v.debt_added AS delta
    FROM referral_reversals v JOIN referral_rewards r USING(capture_id)
    UNION ALL
    SELECT r.referrer_id,-p.amount
    FROM referral_debt_repayments p JOIN referral_rewards r USING(capture_id)
    UNION ALL
    SELECT user_id,-amount FROM referral_restoration_repayments
)
SELECT user_id,sum(delta)::bigint AS outstanding
FROM movements GROUP BY user_id;

-- Keep 052 intact and keep its two existing financial origin checks.
CREATE OR REPLACE FUNCTION verify_referral_debit() RETURNS trigger LANGUAGE plpgsql AS $$
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
    IF NEW.kind='referral_debt_repay' AND EXISTS (
        SELECT 1 FROM referral_restoration_repayments p
        JOIN ledger l ON l.id=p.restoration_id
        WHERE p.ledger_id=NEW.id AND p.user_id=NEW.user_id AND p.amount=-NEW.da
          AND l.user_id=NEW.user_id AND l.mode='live'
          AND l.kind IN ('release','task_release','task_refund','refund_release')
          AND NEW.event_key='referral-restoration-repay:'||p.restoration_id
    ) THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'referral debit origin missing';
END
$$;

DO $install$
DECLARE
    target_schema text := current_schema();
BEGIN
    EXECUTE format($definition$
        CREATE FUNCTION %1$I.repay_restored_referral() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, %1$I, pg_temp
        AS $body$
        DECLARE
            restored bigint;
            debt bigint;
            repayment bigint;
            debit_id uuid := gen_random_uuid();
        BEGIN
            IF TG_RELID<>%2$L::regclass OR TG_WHEN<>'AFTER' OR TG_OP<>'INSERT'
               OR TG_LEVEL<>'ROW' THEN
                RAISE EXCEPTION 'restoration repayment requires the ledger trigger';
            END IF;
            IF NEW.mode<>'live' OR NEW.kind NOT IN ('release','task_release','task_refund','refund_release')
            THEN RETURN NEW; END IF;

            -- The preceding movement and funding triggers already hold the wallet lock.
            SELECT outstanding INTO debt FROM %1$I.referral_debt_balances WHERE user_id=NEW.user_id;
            IF coalesce(debt,0)<=0 THEN RETURN NEW; END IF;
            SELECT coalesce(sum(a.amount),0)::bigint INTO restored
            FROM %1$I.wallet_funding_allocations a
            JOIN %1$I.wallet_funding_lots f ON f.id=a.lot_id
            WHERE f.origin='REFERRAL' AND f.user_id=NEW.user_id AND f.mode=NEW.mode
              AND a.debit_ledger_id=(
                  SELECT id FROM %1$I.ledger
                  WHERE user_id=NEW.user_id AND mode=NEW.mode AND (
                      (NEW.kind='release' AND kind='reserve' AND job_id=NEW.job_id)
                      OR (NEW.kind IN ('task_release','task_refund') AND kind='task_reserve' AND task_quote_id=NEW.task_quote_id)
                      OR (NEW.kind='refund_release' AND kind='refund_hold' AND payment_id=NEW.payment_id)
                  ) ORDER BY created_at DESC,id DESC LIMIT 1
              );
            repayment := least(restored,debt);
            IF repayment<=0 THEN RETURN NEW; END IF;
            INSERT INTO %1$I.referral_restoration_repayments VALUES(NEW.id,NEW.user_id,repayment,debit_id);
            INSERT INTO %1$I.ledger(id,user_id,mode,event_key,kind,da,dr)
            VALUES(debit_id,NEW.user_id,'live','referral-restoration-repay:'||NEW.id,'referral_debt_repay',-repayment,0);
            RETURN NEW;
        END
        $body$
    $definition$, target_schema, format('%I.ledger', target_schema));
    EXECUTE format('REVOKE ALL ON FUNCTION %I.repay_restored_referral() FROM PUBLIC', target_schema);
END
$install$;
CREATE TRIGGER zzzz_referral_restoration_repay AFTER INSERT ON ledger
    FOR EACH ROW WHEN (NEW.mode='live' AND NEW.kind IN ('release','task_release','task_refund','refund_release'))
    EXECUTE FUNCTION repay_restored_referral();

CREATE OR REPLACE FUNCTION verify_referral_debt_repayment() RETURNS trigger LANGUAGE plpgsql AS $$
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
    SELECT coalesce((SELECT outstanding FROM referral_debt_balances WHERE user_id=recipient),0) INTO debt;
    IF NEW.amount<>least(earned,debt) OR EXISTS (
        SELECT 1 FROM referral_reversals WHERE capture_id=NEW.capture_id
    ) THEN RAISE EXCEPTION 'invalid referral debt repayment'; END IF;
    RETURN NEW;
END
$$;
