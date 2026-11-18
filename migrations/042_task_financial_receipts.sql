-- A provider operation is immutable, and belongs to exactly one generation.
CREATE TABLE task_financial_receipts (
    provider text NOT NULL,
    operation_id text NOT NULL CHECK (operation_id <> ''),
    provider_job_id text NOT NULL CHECK (provider_job_id <> ''),
    quote_id uuid NOT NULL REFERENCES task_dispatch(quote_id),
    outcome text NOT NULL CHECK (outcome IN ('charged','full_refund','partial_refund','rejected_unbilled')),
    amount numeric NOT NULL CHECK (amount >= 0 AND amount < 'Infinity'::numeric),
    unit text NOT NULL CHECK (unit <> ''),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (provider,operation_id),
    CHECK ((outcome='rejected_unbilled' AND amount=0) OR (outcome<>'rejected_unbilled' AND amount>0))
);
CREATE INDEX task_receipts_by_quote ON task_financial_receipts(quote_id);
-- Operator readout for terminal generation errors, including jobs without a billing feed.
CREATE VIEW task_failed_billing_review AS
SELECT q.id AS quote_id,q.provider,COALESCE(v.provider_id,i.provider_id) AS provider_job_id,
       CASE WHEN EXISTS (SELECT 1 FROM task_financial_receipts f WHERE f.quote_id=q.id AND f.outcome='full_refund')
                 THEN 'РїРѕР»РЅС‹Р№ РІРѕР·РІСЂР°С‚ РїРѕРґС‚РІРµСЂР¶РґС‘РЅ'
            WHEN EXISTS (SELECT 1 FROM task_financial_receipts f WHERE f.quote_id=q.id AND f.outcome='partial_refund')
                 THEN 'С‡Р°СЃС‚РёС‡РЅС‹Р№ РІРѕР·РІСЂР°С‚ РїРѕРґС‚РІРµСЂР¶РґС‘РЅ'
            WHEN d.state='rejected' OR EXISTS (SELECT 1 FROM task_financial_receipts f WHERE f.quote_id=q.id AND f.outcome='rejected_unbilled')
                 THEN 'РѕС‚РєР°Р· РґРѕ СЃРїРёСЃР°РЅРёСЏ'
            ELSE 'РІРѕР·РІСЂР°С‚ Р°РіСЂРµРіР°С‚РѕСЂР° РЅРµ РїРѕРґС‚РІРµСЂР¶РґС‘РЅ' END AS finding
FROM task_price_quotes q JOIN task_dispatch d ON d.quote_id=q.id
LEFT JOIN video_jobs v ON v.id=q.id
LEFT JOIN anymodel_image_jobs i ON q.provider='anymodel' AND q.operation='images.generate'
    AND i.user_id=q.user_id AND i.update_id=q.update_id
WHERE v.status='failed' OR i.status='failed' OR d.state='rejected';

ALTER TABLE ledger DROP CONSTRAINT ledger_kind_check;
ALTER TABLE ledger ADD CONSTRAINT ledger_kind_check CHECK(kind IN
    ('demo_grant','pilot_grant','payment','reserve','capture','release','refund_hold','refund_release',
     'refund','task_reserve','task_capture','task_release','topup','topup_reversal','topup_debt_repay','task_refund'));
ALTER TABLE ledger DROP CONSTRAINT ledger_task_movement;
ALTER TABLE ledger ADD CONSTRAINT ledger_task_movement CHECK(
    (task_quote_id IS NULL AND kind NOT IN ('task_reserve','task_capture','task_release','task_refund'))
 OR (task_quote_id IS NOT NULL AND mode='live' AND job_id IS NULL AND payment_id IS NULL AND (
        (kind='task_reserve' AND da<0 AND dr=-da)
     OR (kind='task_capture' AND da=0 AND dr<0)
     OR (kind='task_release' AND da>0 AND dr=-da)
     OR (kind='task_refund' AND da>0 AND dr=0)
    ))
);
CREATE UNIQUE INDEX one_task_refund ON ledger(task_quote_id) WHERE kind='task_refund';
-- Keep the original guard for all pre-existing movement kinds.
DROP TRIGGER task_movement ON ledger;
CREATE TRIGGER task_movement BEFORE INSERT ON ledger FOR EACH ROW
    WHEN (NEW.task_quote_id IS NOT NULL AND NEW.kind<>'task_refund') EXECUTE FUNCTION verify_task_movement();
CREATE FUNCTION verify_task_refund() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ledger WHERE task_quote_id=NEW.task_quote_id AND user_id=NEW.user_id
                   AND kind='task_capture' AND dr=-NEW.da)
       OR NOT EXISTS (SELECT 1 FROM task_financial_receipts WHERE quote_id=NEW.task_quote_id AND outcome='full_refund')
    THEN RAISE EXCEPTION 'missing captured charge or full provider refund'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER task_refund_guard BEFORE INSERT ON ledger FOR EACH ROW
    WHEN (NEW.kind='task_refund') EXECUTE FUNCTION verify_task_refund();
