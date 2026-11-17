CREATE TABLE anymodel_speech (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    model_id text NOT NULL,
    title text NOT NULL,
    input text NOT NULL CHECK (char_length(input) BETWEEN 1 AND 4000),
    cost_tokens numeric NOT NULL CHECK (cost_tokens >= 0),
    claimed boolean NOT NULL DEFAULT false,
    audio bytea CHECK (audio IS NULL OR (claimed AND octet_length(audio) BETWEEN 1 AND 20971520)),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes'
);
CREATE INDEX anymodel_speech_owner ON anymodel_speech(user_id,created_at DESC) WHERE audio IS NOT NULL;
CREATE INDEX anymodel_speech_expiry ON anymodel_speech(expires_at);
