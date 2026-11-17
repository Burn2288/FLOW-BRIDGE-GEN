ALTER TABLE task_manual_tariffs DROP CONSTRAINT task_manual_tariffs_basis_check;
ALTER TABLE task_manual_tariffs ADD COLUMN output_amount numeric
    CHECK (output_amount BETWEEN 0 AND 1000000000000);
ALTER TABLE task_manual_tariffs ADD CONSTRAINT task_manual_tariffs_operation_basis CHECK (
    basis='request'
    OR (basis='utf16' AND operation='audio.speech')
    OR (basis='image' AND operation='images.generate')
    OR (basis IN ('second','started_minute') AND operation='video')
    OR (basis='token' AND operation='chat')
);
ALTER TABLE task_manual_tariffs ADD CONSTRAINT task_manual_tariffs_directional_amount
    CHECK ((basis='token') = (output_amount IS NOT NULL));

-- Quotes keep the source amount. A video tariff may use a unit without a USD equivalent.
ALTER TABLE video_jobs ALTER COLUMN cost_usd DROP NOT NULL;
