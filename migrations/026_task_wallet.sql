ALTER TABLE ledger ADD COLUMN task_quote_id uuid REFERENCES task_dispatch(quote_id);
ALTER TABLE ledger DROP CONSTRAINT ledger_kind_check;
ALTER TABLE ledger ADD CONSTRAINT ledger_kind_check
    CHECK(kind IN ('demo_grant','pilot_grant','payment','reserve','capture','release',
                   'refund_hold','refund_release','refund','task_reserve','task_capture','task_release'));
ALTER TABLE ledger ADD CONSTRAINT ledger_task_movement CHECK(
    (task_quote_id IS NULL AND kind NOT IN ('task_reserve','task_capture','task_release'))
 OR (task_quote_id IS NOT NULL AND mode='live' AND job_id IS NULL AND payment_id IS NULL AND (
        (kind='task_reserve' AND da<0 AND dr=-da)
     OR (kind='task_capture' AND da=0 AND dr<0)
     OR (kind='task_release' AND da>0 AND dr=-da)
    ))
);
ALTER TABLE ledger DROP CONSTRAINT ledger_movement_shape;
ALTER TABLE ledger ADD CONSTRAINT ledger_movement_shape CHECK(
    task_quote_id IS NOT NULL
 OR (kind='reserve' AND da<0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind='capture' AND da=0 AND dr<0 AND job_id IS NOT NULL)
 OR (kind='release' AND da>0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind IN ('demo_grant','payment') AND da>0 AND dr=0)
 OR (kind='pilot_grant' AND mode='live' AND da BETWEEN 1 AND 3000 AND dr=0 AND job_id IS NULL AND payment_id IS NULL)
 OR (kind='refund_hold' AND da<0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund_release' AND da>0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund' AND da=0 AND dr<0 AND payment_id IS NOT NULL)
);
CREATE UNIQUE INDEX one_task_reserve ON ledger(task_quote_id) WHERE kind='task_reserve';
CREATE UNIQUE INDEX one_task_settlement ON ledger(task_quote_id) WHERE kind IN ('task_capture','task_release');
CREATE FUNCTION verify_task_movement() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM task_price_quotes q
        WHERE q.id=NEW.task_quote_id AND q.user_id=NEW.user_id AND (q.price->>'total')::numeric=abs(NEW.dr)
    ) THEN RAISE EXCEPTION 'task movement mismatch'; END IF;
    IF NEW.kind<>'task_reserve' AND NOT EXISTS (
        SELECT 1 FROM ledger r WHERE r.task_quote_id=NEW.task_quote_id AND r.kind='task_reserve'
    ) THEN RAISE EXCEPTION 'task reservation missing'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER task_movement BEFORE INSERT ON ledger
    FOR EACH ROW WHEN (NEW.task_quote_id IS NOT NULL) EXECUTE FUNCTION verify_task_movement();
