-- A manual review records evidence but does not settle the user's financial claim.
ALTER TABLE task_financial_reconciliation_cases
    DROP CONSTRAINT task_financial_reconciliation_cases_status_check,
    DROP CONSTRAINT task_financial_reconciliation_cases_resolved_at_check,
    DROP CONSTRAINT task_financial_reconciliation_manual_review,
    ADD COLUMN manual_reviewed_at timestamptz,
    ADD COLUMN final_evidence_ref text,
    ADD COLUMN final_reviewer_external_id bigint;

UPDATE task_financial_reconciliation_cases
SET manual_reviewed_at=resolved_at,
    status='required',
    resolved_at=NULL,
    finding='manual_evidence_recorded_pending_resolution'
WHERE status='manual_reviewed';

ALTER TABLE task_financial_reconciliation_cases
    ADD CONSTRAINT task_financial_reconciliation_cases_status_check
        CHECK (status IN ('required','resolved','resolved_no_refund')),
    ADD CONSTRAINT task_financial_reconciliation_cases_resolved_at_check
        CHECK ((status='required') = (resolved_at IS NULL)),
    ADD CONSTRAINT task_financial_reconciliation_manual_review CHECK (
        (manual_operation_id IS NULL AND manual_amount IS NULL AND manual_unit IS NULL
         AND manual_evidence_ref IS NULL AND manual_reviewer_external_id IS NULL AND manual_reviewed_at IS NULL)
        OR
        (manual_operation_id IS NOT NULL AND manual_amount IS NOT NULL AND manual_unit IS NOT NULL
         AND manual_evidence_ref IS NOT NULL AND manual_reviewer_external_id IS NOT NULL AND manual_reviewed_at IS NOT NULL)
    ),
    ADD CONSTRAINT task_financial_reconciliation_no_refund_resolution CHECK (
        (status='resolved_no_refund' AND final_evidence_ref IS NOT NULL AND final_reviewer_external_id IS NOT NULL)
        OR
        (status<>'resolved_no_refund' AND final_evidence_ref IS NULL AND final_reviewer_external_id IS NULL)
    ),
    ADD CONSTRAINT task_financial_reconciliation_final_actor CHECK
        (final_reviewer_external_id IS NULL OR final_reviewer_external_id > 0);

ALTER TABLE task_financial_reconciliation_manual_audit
    ADD COLUMN action text NOT NULL DEFAULT 'review',
    ADD CONSTRAINT task_financial_reconciliation_manual_audit_action CHECK
        (action IN ('review','no_refund_resolution'));

CREATE OR REPLACE VIEW task_financial_reconciliation_queue AS
    SELECT quote_id,provider,provider_job_id,finding,attempts,first_seen_at,last_seen_at,
           manual_reviewed_at,manual_evidence_ref
    FROM task_financial_reconciliation_cases WHERE status='required';
