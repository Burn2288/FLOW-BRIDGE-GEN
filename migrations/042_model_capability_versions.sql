CREATE TABLE model_capability_versions (
    provider text NOT NULL,
    model_id text NOT NULL,
    operation text NOT NULL,
    version uuid NOT NULL,
    schema jsonb NOT NULL,
    published boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(provider, model_id, operation, version)
);
CREATE UNIQUE INDEX model_capability_one_published
    ON model_capability_versions(provider, model_id, operation) WHERE published;
