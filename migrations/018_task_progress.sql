ALTER TABLE video_jobs
    ADD COLUMN provider_progress smallint CHECK (provider_progress BETWEEN 0 AND 100),
    ADD COLUMN provider_stage text;

CREATE TABLE task_progress (
    chat_id bigint NOT NULL,
    message_id bigint NOT NULL,
    model text NOT NULL,
    video_id uuid UNIQUE REFERENCES video_jobs(id) ON DELETE CASCADE,
    image_id bigint UNIQUE REFERENCES anymodel_image_jobs(update_id) ON DELETE CASCADE,
    last_text text NOT NULL,
    PRIMARY KEY (chat_id, message_id),
    CHECK (num_nonnulls(video_id, image_id) = 1)
);
