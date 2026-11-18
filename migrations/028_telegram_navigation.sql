CREATE TABLE telegram_navigation (
    chat_id bigint PRIMARY KEY,
    active_id bigint,
    animation text,
    keyboard_id bigint,
    keyboard_labels text[] NOT NULL DEFAULT '{}',
    stale_ids bigint[] NOT NULL DEFAULT '{}'
);
