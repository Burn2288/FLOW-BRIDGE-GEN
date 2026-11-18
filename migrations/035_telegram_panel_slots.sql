ALTER TABLE telegram_navigation
    ADD COLUMN active_panel text,
    ADD COLUMN panel_ids jsonb NOT NULL DEFAULT '{}';
