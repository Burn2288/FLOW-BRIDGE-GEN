CREATE TABLE task_manual_tariffs (
    provider text NOT NULL,
    model_id text NOT NULL,
    operation text NOT NULL,
    params jsonb NOT NULL CHECK (jsonb_typeof(params) = 'object'),
    basis text NOT NULL CHECK (basis IN ('request','utf16')),
    source_unit text NOT NULL REFERENCES task_price_rates(source_unit),
    amount numeric NOT NULL CHECK (amount BETWEEN 0 AND 1000000000000),
    expires_at timestamptz NOT NULL,
    evidence text NOT NULL CHECK (length(evidence) BETWEEN 1 AND 200),
    revision bigint NOT NULL DEFAULT nextval('task_price_rule_revision'),
    admin_id uuid NOT NULL REFERENCES users(id),
    PRIMARY KEY (provider,model_id,operation,params),
    CHECK (basis <> 'utf16' OR operation = 'audio.speech')
);

CREATE TABLE task_chat_works (
    quote_id uuid PRIMARY KEY REFERENCES task_price_quotes(id) ON DELETE CASCADE,
    answer text NOT NULL CHECK (length(answer) BETWEEN 1 AND 100000),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days'
);

ALTER TABLE anymodel_speech RENAME TO task_speech_works;
ALTER TABLE task_speech_works ADD COLUMN provider text NOT NULL DEFAULT 'anymodel'
    CHECK (provider IN ('anymodel','clodex'));

-- Keep historical read queries and operations tooling compatible.
CREATE VIEW anymodel_speech AS SELECT id,user_id,model_id,title,input,cost_tokens,claimed,audio,
    created_at,expires_at FROM task_speech_works WHERE provider='anymodel';
