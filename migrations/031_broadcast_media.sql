ALTER TABLE telegram_broadcasts RENAME COLUMN photo_id TO media_file_id;

ALTER TABLE telegram_broadcasts
    ADD COLUMN media_kind text,
    ADD COLUMN media_spoiler boolean NOT NULL DEFAULT false,
    ADD COLUMN caption_above_media boolean NOT NULL DEFAULT false;

UPDATE telegram_broadcasts SET media_kind='photo' WHERE media_file_id IS NOT NULL;

ALTER TABLE telegram_broadcasts ADD CHECK (
    (media_kind IS NULL AND media_file_id IS NULL)
    OR (media_kind IS NOT NULL AND media_file_id IS NOT NULL AND media_kind IN (
        'photo','animation','video','audio','voice','document','sticker','video_note'
    ))
);
