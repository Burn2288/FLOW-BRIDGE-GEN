-- 040 is reserved by Burn2288's independent admission candidate (#38).
-- Forward-only, additive delivery metadata; generation/ledger states are unchanged.
CREATE TABLE task_media_delivery (
    kind text NOT NULL CHECK (kind IN ('video','image')),
    job_id text NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id),
    claim_id uuid NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('unknown','sent','rejected')),
    message_id bigint,
    error_code text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kind,job_id)
);

-- Historical attempts have no receipt. Do not guess they were rejected.
INSERT INTO task_media_delivery(kind,job_id,user_id,claim_id,outcome)
SELECT 'video',id::text,user_id,gen_random_uuid(),
       CASE WHEN notify_at IS NULL THEN 'sent' ELSE 'unknown' END
FROM video_jobs WHERE notify_attempts>0;
INSERT INTO task_media_delivery(kind,job_id,user_id,claim_id,outcome)
SELECT 'image',update_id::text,user_id,gen_random_uuid(),
       CASE WHEN status='delivered' THEN 'sent' ELSE 'unknown' END
FROM anymodel_image_jobs WHERE notify_attempts>0 AND status IN ('ready','delivered');
UPDATE video_jobs SET notify_attempts=3 WHERE notify_attempts>0 AND notify_at IS NOT NULL;
UPDATE anymodel_image_jobs SET notify_attempts=3 WHERE notify_attempts>0 AND status='ready';
