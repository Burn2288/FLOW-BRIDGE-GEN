ALTER TABLE conversations ADD COLUMN aggregate_context jsonb;
ALTER TABLE conversations ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
