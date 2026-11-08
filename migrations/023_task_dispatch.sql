CREATE TABLE task_dispatch (
    quote_id uuid PRIMARY KEY REFERENCES task_price_quotes(id),
    state text NOT NULL CHECK (state IN ('pending','dispatching','completed','delegated','interrupted','uncertain')),
    recovery_notice boolean NOT NULL DEFAULT false
);
CREATE INDEX task_dispatch_unfinished ON task_dispatch(state) WHERE state IN ('pending','dispatching');
