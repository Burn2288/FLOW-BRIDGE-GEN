-- A scoped proof of the Telegram owner's active Admin Edition session.
CREATE TABLE miniapp_music_sessions (
    chat_id bigint PRIMARY KEY,
    backend_pid integer NOT NULL,
    backend_started_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    password_tag bytea NOT NULL
);
