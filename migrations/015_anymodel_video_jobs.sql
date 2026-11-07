ALTER TABLE video_jobs
    ADD COLUMN provider text NOT NULL DEFAULT 'clodex' CHECK (provider IN ('clodex','anymodel')),
    ADD COLUMN idempotency_key uuid,
    ADD COLUMN connection_id text,
    ADD COLUMN key_fingerprint text,
    DROP CONSTRAINT video_jobs_provider_id_key,
    ADD UNIQUE (provider,provider_id);
