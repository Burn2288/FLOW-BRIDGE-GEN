ALTER TABLE jobs ADD COLUMN model_id text;

CREATE TABLE image_works (
    id uuid PRIMARY KEY,
    update_id bigint NOT NULL UNIQUE,
    user_id uuid NOT NULL REFERENCES users(id),
    model_id text NOT NULL,
    prompt text NOT NULL CHECK (char_length(prompt) BETWEEN 1 AND 6000),
    image bytea NOT NULL CHECK (octet_length(image) BETWEEN 1 AND 5242880),
    filename text NOT NULL CHECK (filename IN ('result.png','result.jpg','test.png')),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days'
);
CREATE INDEX image_works_owner ON image_works(user_id,created_at DESC);
CREATE INDEX image_works_expiry ON image_works(expires_at);
