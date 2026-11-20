-- Durable operator queue for provider billing states that cannot be proven automatically.
CREATE TABLE task_financial_reconciliation_cases (
    quote_id uuid PRIMARY KEY REFERENCES task_dispatch(quote_id),
    provider text NOT NULL,
    provider_job_id text,
    status text NOT NULL DEFAULT 'required' CHECK (status IN ('required','resolved')),
    finding text NOT NULL CHECK (finding <> ''),
    attempts integer NOT NULL DEFAULT 1 CHECK (attempts > 0),
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    resolution_operation_id text,
    FOREIGN KEY (provider,resolution_operation_id)
        REFERENCES task_financial_receipts(provider,operation_id),
    CHECK ((status='resolved') = (resolved_at IS NOT NULL)),
    CHECK ((status='resolved') = (resolution_operation_id IS NOT NULL))
);
CREATE INDEX task_financial_reconciliation_open
    ON task_financial_reconciliation_cases(last_seen_at,quote_id) WHERE status='required';
CREATE VIEW task_financial_reconciliation_queue AS
    SELECT quote_id,provider,provider_job_id,finding,attempts,first_seen_at,last_seen_at
    FROM task_financial_reconciliation_cases WHERE status='required';
