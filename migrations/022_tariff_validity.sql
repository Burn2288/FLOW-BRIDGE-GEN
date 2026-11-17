ALTER TABLE task_manual_tariffs
    ALTER COLUMN expires_at DROP NOT NULL,
    ADD COLUMN enabled boolean NOT NULL DEFAULT true,
    ADD COLUMN temporary boolean NOT NULL DEFAULT false,
    ADD COLUMN verified_at timestamptz DEFAULT clock_timestamp();

-- Historical rows did not record a verification date.
UPDATE task_manual_tariffs SET verified_at=NULL;

ALTER TABLE task_manual_tariffs ADD CONSTRAINT temporary_tariff_has_expiry
    CHECK (NOT temporary OR expires_at IS NOT NULL);
