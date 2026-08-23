CREATE TABLE weekly_posts (
    channel_key TEXT NOT NULL,
    iso_week TEXT NOT NULL,
    chat_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (channel_key, iso_week)
);

CREATE TABLE bot_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    weekly_paused BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO bot_state (id, weekly_paused) VALUES (1, FALSE);
