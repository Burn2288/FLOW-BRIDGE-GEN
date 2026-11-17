CREATE TABLE interaction_attempts (
    update_id bigint PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
