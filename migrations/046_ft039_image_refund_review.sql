ALTER TABLE image_works DROP CONSTRAINT image_works_filename_check;
ALTER TABLE image_works ADD CONSTRAINT image_works_filename_check
    CHECK (filename IN ('result.png','result.jpg','result.bin','test.png'));

ALTER TABLE task_financial_receipts ADD COLUMN refunded_operation_id text,
    ADD CONSTRAINT task_financial_receipt_refund_link
        CHECK ((outcome IN ('full_refund','partial_refund')) = (refunded_operation_id IS NOT NULL)) NOT VALID,
    ADD CONSTRAINT task_financial_receipt_refund_charge_fk
        FOREIGN KEY (provider,refunded_operation_id)
        REFERENCES task_financial_receipts(provider,operation_id);

CREATE FUNCTION verify_task_financial_receipt_refund() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE charge task_financial_receipts%ROWTYPE;
BEGIN
    IF NEW.outcome NOT IN ('full_refund','partial_refund') THEN RETURN NEW; END IF;
    SELECT * INTO charge FROM task_financial_receipts
      WHERE provider=NEW.provider AND operation_id=NEW.refunded_operation_id FOR SHARE;
    IF NOT FOUND OR charge.outcome<>'charged' OR charge.quote_id<>NEW.quote_id
       OR charge.provider_job_id IS DISTINCT FROM NEW.provider_job_id
       OR charge.unit<>NEW.unit OR NEW.amount>charge.amount
       OR (NEW.outcome='full_refund' AND NEW.amount<>charge.amount)
    THEN RAISE EXCEPTION 'provider refund is not bound to its charge'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER task_financial_receipt_refund_guard
    BEFORE INSERT OR UPDATE ON task_financial_receipts
    FOR EACH ROW EXECUTE FUNCTION verify_task_financial_receipt_refund();

CREATE FUNCTION prevent_task_financial_receipt_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'provider financial receipt is immutable';
END $$;
CREATE TRIGGER task_financial_receipt_immutable
    BEFORE UPDATE OR DELETE ON task_financial_receipts
    FOR EACH ROW EXECUTE FUNCTION prevent_task_financial_receipt_mutation();

ALTER TABLE task_financial_reconciliation_cases
    DROP CONSTRAINT task_financial_reconciliation_cases_status_check,
    DROP CONSTRAINT task_financial_reconciliation_cases_check,
    ADD CONSTRAINT task_financial_reconciliation_cases_status_check
        CHECK (status IN ('required','resolved','manual_reviewed')),
    ADD CONSTRAINT task_financial_reconciliation_cases_resolved_at_check
        CHECK ((status='required') = (resolved_at IS NULL)),
    ADD COLUMN manual_operation_id text,
    ADD COLUMN manual_amount numeric,
    ADD COLUMN manual_unit text,
    ADD COLUMN manual_evidence_ref text,
    ADD COLUMN manual_reviewer_external_id bigint,
    ADD CONSTRAINT task_financial_reconciliation_manual_review CHECK (
        (status='manual_reviewed') = (manual_operation_id IS NOT NULL AND manual_amount IS NOT NULL
            AND manual_unit IS NOT NULL AND manual_evidence_ref IS NOT NULL
            AND manual_reviewer_external_id IS NOT NULL)
    ),
    ADD CONSTRAINT task_financial_reconciliation_manual_amount CHECK
        (manual_amount IS NULL OR (manual_amount > 0 AND manual_amount < 'Infinity'::numeric)),
    ADD CONSTRAINT task_financial_reconciliation_manual_actor CHECK
        (manual_reviewer_external_id IS NULL OR manual_reviewer_external_id > 0);

CREATE TABLE task_financial_reconciliation_manual_audit (
    provider text NOT NULL,
    operation_id text NOT NULL CHECK (operation_id ~ '^[A-Za-z0-9._:-]{1,200}$'),
    quote_id uuid NOT NULL REFERENCES task_financial_reconciliation_cases(quote_id),
    amount numeric NOT NULL CHECK (amount > 0 AND amount < 'Infinity'::numeric),
    unit text NOT NULL CHECK (unit ~ '^[A-Za-z0-9._:-]{1,100}$'),
    evidence_ref text NOT NULL CHECK (char_length(evidence_ref) BETWEEN 8 AND 500),
    reviewer_external_id bigint NOT NULL CHECK (reviewer_external_id > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(provider,operation_id),
    UNIQUE(quote_id,operation_id)
);

CREATE FUNCTION prevent_manual_reconciliation_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'manual reconciliation audit is immutable';
END $$;
CREATE TRIGGER task_financial_reconciliation_audit_immutable
    BEFORE UPDATE OR DELETE ON task_financial_reconciliation_manual_audit
    FOR EACH ROW EXECUTE FUNCTION prevent_manual_reconciliation_audit_mutation();

CREATE OR REPLACE VIEW task_financial_reconciliation_queue AS
    SELECT quote_id,provider,provider_job_id,finding,attempts,first_seen_at,last_seen_at
    FROM task_financial_reconciliation_cases WHERE status='required';
