CREATE TABLE miniapp_sessions (
    token_hash bytea PRIMARY KEY,
    init_hash bytea UNIQUE NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT false
);
CREATE INDEX miniapp_sessions_expiry ON miniapp_sessions(expires_at);
