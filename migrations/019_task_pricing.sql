CREATE SEQUENCE task_price_rule_revision;

CREATE TABLE task_price_rules (
    provider text NOT NULL DEFAULT '',
    model_id text NOT NULL DEFAULT '',
    kind text NOT NULL CHECK (kind IN ('percent','fixed')),
    amount numeric NOT NULL CHECK (amount >= 0 AND amount <= 1000000000000),
    revision bigint NOT NULL DEFAULT nextval('task_price_rule_revision'),
    PRIMARY KEY (provider,model_id),
    CHECK (provider <> '' OR model_id = '')
);

CREATE TABLE task_price_rates (
    source_unit text PRIMARY KEY,
    multiplier numeric NOT NULL CHECK (multiplier > 0 AND multiplier <= 1000000000000),
    revision bigint NOT NULL DEFAULT nextval('task_price_rule_revision')
);
INSERT INTO task_price_rates(source_unit,multiplier) VALUES ('anymodel_balance_token',1);

CREATE TABLE task_price_quotes (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id),
    provider text NOT NULL,
    model_id text NOT NULL,
    operation text NOT NULL,
    request jsonb NOT NULL,
    price jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','superseded','cancelled','accepted')),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes',
    accepted_at timestamptz,
    update_id bigint UNIQUE
);
CREATE INDEX task_price_quotes_accepted ON task_price_quotes(accepted_at) WHERE state='accepted';

-- Reconcile only from confirmed accounting evidence. Amounts are in the quote's bot unit,
-- except provider_cost which is in the original source unit.
CREATE TABLE task_price_accounting (
    quote_id uuid PRIMARY KEY REFERENCES task_price_quotes(id),
    user_debit numeric NOT NULL CHECK (user_debit >= 0),
    user_refund numeric NOT NULL CHECK (user_refund BETWEEN 0 AND user_debit),
    provider_cost numeric CHECK (provider_cost >= 0),
    reference text NOT NULL CHECK (length(reference) BETWEEN 1 AND 200)
);

ALTER TABLE anymodel_image_jobs ADD COLUMN model_id text NOT NULL DEFAULT 'anymedia/fibo-2';
