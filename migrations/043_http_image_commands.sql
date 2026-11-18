-- HTTP command identity is separate from Telegram update IDs.
CREATE SEQUENCE http_image_correlation_seq START WITH 4611686018427387904 MAXVALUE 9223372036854775807;
CREATE TABLE http_image_commands (
    user_id uuid NOT NULL REFERENCES users(id),
    idempotency_key text NOT NULL,
    quote_id uuid NOT NULL REFERENCES task_price_quotes(id),
    correlation_id bigint NOT NULL UNIQUE CHECK (correlation_id < 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, idempotency_key),
    UNIQUE (quote_id)
);
