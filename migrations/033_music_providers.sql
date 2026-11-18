ALTER TABLE clodex_music_jobs
    ADD COLUMN provider text NOT NULL DEFAULT 'clodex',
    DROP CONSTRAINT clodex_music_jobs_user_id_key,
    DROP CONSTRAINT clodex_music_jobs_provider_id_key,
    ADD UNIQUE (provider,user_id),
    ADD UNIQUE (provider,provider_id);

ALTER TABLE clodex_music_ledger
    ADD COLUMN provider text NOT NULL DEFAULT 'clodex',
    DROP CONSTRAINT clodex_music_ledger_pkey,
    ADD PRIMARY KEY (provider,user_id,kind);

DROP INDEX clodex_music_settlement;
CREATE UNIQUE INDEX clodex_music_settlement ON clodex_music_ledger(provider,user_id)
WHERE kind IN ('capture','release');


ALTER TABLE approved_models
    DROP CONSTRAINT approved_models_operation_check,
    ADD CHECK (operation IN ('chat','images.generate','video','audio.speech','audio.generate'));
