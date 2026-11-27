-- A reservation pins the approved test policy; this migration posts no reward.
CREATE TABLE referral_policy_snapshots (
    reserve_ledger_id uuid PRIMARY KEY REFERENCES ledger(id),
    quote_id uuid NOT NULL UNIQUE REFERENCES task_price_quotes(id),
    policy_version text NOT NULL CHECK (policy_version='C-011-v1-functional-test'),
    rate_bps integer NOT NULL CHECK (rate_bps=500),
    owner_decision text NOT NULL CHECK (owner_decision='D-07'),
    effective_at timestamptz NOT NULL
);
CREATE TRIGGER referral_policy_snapshot_immutable
    BEFORE UPDATE OR DELETE ON referral_policy_snapshots
    FOR EACH ROW EXECUTE FUNCTION immutable_row();

DO $install$
DECLARE
    target_schema text := current_schema();
BEGIN
    EXECUTE format($definition$
        CREATE FUNCTION %1$I.pin_referral_policy() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF TG_RELID <> %2$L::regclass OR TG_WHEN <> 'AFTER'
               OR TG_OP <> 'INSERT' OR TG_LEVEL <> 'ROW' OR NEW.kind <> 'task_reserve'
            THEN RAISE EXCEPTION 'policy snapshot requires task reservation'; END IF;
            INSERT INTO %1$I.referral_policy_snapshots
            VALUES(NEW.id, NEW.task_quote_id, 'C-011-v1-functional-test', 500, 'D-07', NEW.created_at);
            RETURN NEW;
        END
        $function$
    $definition$, target_schema, format('%I.ledger', target_schema));
    EXECUTE format('REVOKE ALL ON FUNCTION %I.pin_referral_policy() FROM PUBLIC', target_schema);
END
$install$;

CREATE TRIGGER zz_pin_referral_policy AFTER INSERT ON ledger
    FOR EACH ROW WHEN (NEW.kind='task_reserve') EXECUTE FUNCTION pin_referral_policy();
