-- Users table
CREATE TABLE users (
    user_id      BIGINT PRIMARY KEY,
    username     TEXT,
    display_name TEXT,
    role         TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'gm', 'user')),
    slots        INTEGER NOT NULL DEFAULT 1,
    slots_week   TEXT NOT NULL
);

CREATE INDEX idx_users_username ON users (LOWER(username));

-- Sequence for game ID generation
CREATE SEQUENCE game_id_seq;

-- Games table
CREATE TABLE games (
    game_id     TEXT PRIMARY KEY,
    creator_id  BIGINT NOT NULL REFERENCES users(user_id),
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    max_players INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    game_date   TEXT,
    message_id  BIGINT,
    photo_id    TEXT,
    autodelete  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_games_creator ON games (creator_id);
CREATE INDEX idx_games_message_id ON games (message_id) WHERE message_id IS NOT NULL;

-- Game players (many-to-many)
CREATE TABLE game_players (
    game_id   TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    user_id   BIGINT NOT NULL REFERENCES users(user_id),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, user_id)
);

CREATE INDEX idx_game_players_user ON game_players (user_id);

-- Game media files
CREATE TABLE game_media (
    id        SERIAL PRIMARY KEY,
    game_id   TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL
);

CREATE INDEX idx_game_media_game ON game_media (game_id);
