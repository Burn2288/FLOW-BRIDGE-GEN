CREATE TABLE telegram_panel_callbacks (
    chat_id bigint NOT NULL REFERENCES telegram_navigation(chat_id) ON DELETE CASCADE,
    message_id bigint NOT NULL,
    routes text[] NOT NULL,
    PRIMARY KEY (chat_id, message_id)
);
