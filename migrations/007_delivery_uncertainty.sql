ALTER TABLE deliveries DROP CONSTRAINT deliveries_status_check;
ALTER TABLE deliveries ADD CONSTRAINT deliveries_status_check
    CHECK (status IN ('pending','sending','sent','retry','expired','uncertain'));

-- Older workers retried transport failures without knowing whether Telegram accepted the file.
UPDATE deliveries
SET status = 'uncertain', lease_until = NULL
WHERE status IN ('sending','retry');
