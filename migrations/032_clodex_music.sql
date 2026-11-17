CREATE TABLE clodex_music_jobs (
    id uuid PRIMARY KEY REFERENCES task_price_quotes(id),
    user_id uuid NOT NULL UNIQUE REFERENCES users(id),
    chat_id bigint NOT NULL,
    status text NOT NULL CHECK (status IN (
        'queued','submitting','polling','ready','delivering','delivered','delivery_unknown','failed','unknown'
    )),
    provider_id text UNIQUE,
    last_error text,
    next_at timestamptz NOT NULL DEFAULT now(),
    status_message_id bigint,
    mp3 bytea,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days'
);

CREATE TABLE clodex_music_ledger (
    user_id uuid NOT NULL REFERENCES users(id),
    quote_id uuid NOT NULL REFERENCES task_price_quotes(id),
    kind text NOT NULL,
    da bigint NOT NULL,
    dr bigint NOT NULL,
    PRIMARY KEY (user_id,kind),
    CHECK ((kind='credit' AND da>0 AND dr=0)
        OR (kind='reserve' AND da<0 AND dr=-da)
        OR (kind='capture' AND da=0 AND dr<0)
        OR (kind='release' AND da>0 AND dr=-da))
);

CREATE UNIQUE INDEX clodex_music_settlement ON clodex_music_ledger(user_id)
WHERE kind IN ('capture','release');

CREATE TRIGGER clodex_music_ledger_immutable BEFORE UPDATE OR DELETE ON clodex_music_ledger
FOR EACH ROW EXECUTE FUNCTION immutable_row();
