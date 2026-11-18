CREATE TABLE anymodel_image_jobs (
    update_id bigint PRIMARY KEY REFERENCES interaction_attempts(update_id),
    user_id uuid NOT NULL REFERENCES users(id),
    prompt text NOT NULL,
    provider_id text UNIQUE,
    status text NOT NULL CHECK (status IN ('submitting','pending','ready','delivered','failed','unknown')),
    next_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days',
    notify_attempts integer NOT NULL DEFAULT 0,
    CHECK (status <> 'pending' OR provider_id IS NOT NULL)
);
CREATE INDEX anymodel_image_jobs_due ON anymodel_image_jobs(next_at) WHERE status IN ('pending','ready');
