-- The earlier gateway delivered some files without acknowledging them.
-- A fresh Telegram confirmation opts in without replaying that backlog.
ALTER TABLE jobs ADD COLUMN telegram_delivery boolean NOT NULL DEFAULT false;
