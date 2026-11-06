CREATE TABLE video_jobs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    model_id text NOT NULL,
    prompt text NOT NULL,
    cost_usd numeric NOT NULL CHECK (cost_usd >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    quote_expires_at timestamptz NOT NULL DEFAULT now() + interval '5 minutes',
    status text NOT NULL DEFAULT 'quoted'
        CHECK (status IN ('quoted','submitting','polling','succeeded','failed','uncertain')),
    provider_id text UNIQUE,
    next_poll_at timestamptz,
    video bytea CHECK (octet_length(video) BETWEEN 12 AND 49000000),
    notify_at timestamptz,
    notify_attempts smallint NOT NULL DEFAULT 0,
    expires_at timestamptz
);
CREATE INDEX video_jobs_due ON video_jobs(next_poll_at) WHERE status = 'polling';
CREATE INDEX video_jobs_history ON video_jobs(user_id,created_at DESC) WHERE status = 'succeeded';
CREATE INDEX video_jobs_notifications ON video_jobs(notify_at) WHERE notify_at IS NOT NULL;
