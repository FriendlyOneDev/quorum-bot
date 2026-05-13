CREATE TABLE game_interested (
    game_id   TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    user_id   BIGINT NOT NULL REFERENCES users(user_id),
    marked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, user_id)
);

ALTER TABLE users ADD COLUMN notify_interested BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE games ADD COLUMN interested_notified BOOLEAN NOT NULL DEFAULT FALSE;
