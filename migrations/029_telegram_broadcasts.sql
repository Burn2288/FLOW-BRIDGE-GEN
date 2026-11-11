ALTER TABLE identities
    ADD COLUMN telegram_private boolean NOT NULL DEFAULT false,
    ADD COLUMN broadcast_opt_out boolean NOT NULL DEFAULT false;

UPDATE identities SET telegram_private=true
WHERE platform='telegram' AND welcome_message_id IS NOT NULL;

CREATE TABLE telegram_broadcasts (
    id uuid PRIMARY KEY,
    owner_chat bigint NOT NULL,
    state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft','cancelled','running','done','stopped')),
    revision integer NOT NULL DEFAULT 0,
    awaiting_post boolean NOT NULL DEFAULT true,
    body text,
    photo_id text,
    entities jsonb NOT NULL DEFAULT '[]',
    audience text CHECK (audience IN ('self','all')),
    expected_count integer,
    report_id bigint,
    report_at timestamptz,
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX telegram_broadcast_one_draft
    ON telegram_broadcasts(owner_chat) WHERE state='draft';

CREATE TABLE telegram_broadcast_deliveries (
    broadcast_id uuid NOT NULL REFERENCES telegram_broadcasts(id),
    chat_id bigint NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','sending','sent','unavailable','error','unknown','stopped','opted_out'
    )),
    message_id bigint,
    retry_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(broadcast_id,chat_id)
);

CREATE INDEX telegram_broadcast_pending
    ON telegram_broadcast_deliveries(broadcast_id,chat_id) WHERE status='pending';

CREATE TABLE telegram_broadcast_throttle (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    resume_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO telegram_broadcast_throttle DEFAULT VALUES;
