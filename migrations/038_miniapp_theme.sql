ALTER TABLE users ADD COLUMN miniapp_theme text NOT NULL DEFAULT 'dark'
    CHECK (miniapp_theme IN ('dark', 'light'));
