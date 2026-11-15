ALTER TABLE inbox ADD COLUMN dispatch_attempts smallint NOT NULL DEFAULT 0;
CREATE INDEX inbox_unprocessed_idx ON inbox(update_id) WHERE NOT done
    AND error_code IS DISTINCT FROM 'RETRY_REVIEW';
