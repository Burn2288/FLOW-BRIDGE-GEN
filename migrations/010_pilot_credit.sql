-- Keep operator-funded test credits distinct from provider payments.
DO $$
DECLARE shape_constraint name;
BEGIN
    SELECT conname INTO STRICT shape_constraint
    FROM pg_constraint
    WHERE conrelid='ledger'::regclass AND contype='c'
      AND pg_get_constraintdef(oid) LIKE '%demo_grant%'
      AND pg_get_constraintdef(oid) LIKE '%da > 0%';
    EXECUTE format('ALTER TABLE ledger DROP CONSTRAINT %I', shape_constraint);
END $$;
ALTER TABLE ledger DROP CONSTRAINT ledger_kind_check;
ALTER TABLE ledger ADD CONSTRAINT ledger_kind_check
    CHECK(kind IN ('demo_grant','pilot_grant','payment','reserve','capture','release','refund_hold','refund_release','refund'));
ALTER TABLE ledger ADD CONSTRAINT ledger_movement_shape CHECK(
    (kind='reserve' AND da<0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind='capture' AND da=0 AND dr<0 AND job_id IS NOT NULL)
 OR (kind='release' AND da>0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind IN ('demo_grant','payment') AND da>0 AND dr=0)
 OR (kind='pilot_grant' AND mode='live' AND da BETWEEN 1 AND 3000 AND dr=0 AND job_id IS NULL AND payment_id IS NULL)
 OR (kind='refund_hold' AND da<0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund_release' AND da>0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund' AND da=0 AND dr<0 AND payment_id IS NOT NULL));
