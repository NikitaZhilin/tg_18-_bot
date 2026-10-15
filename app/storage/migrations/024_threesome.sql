-- Hidden «игра на троих» (enabled by an admin, group only).
-- A third player slot: SQLite cannot change a CHECK, so the slot columns are
-- re-created with 'player_3' allowed and their values copied over.

CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_by INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE sessions ADD COLUMN player_3_id INTEGER;
ALTER TABLE sessions ADD COLUMN play_mode TEXT NOT NULL DEFAULT 'couple'
    CHECK (play_mode IN ('couple', 'threesome'));

ALTER TABLE sessions RENAME COLUMN current_player_slot TO current_player_slot_old;
ALTER TABLE sessions ADD COLUMN current_player_slot TEXT NOT NULL DEFAULT 'player_1'
    CHECK (current_player_slot IN ('player_1', 'player_2', 'player_3'));
UPDATE sessions SET current_player_slot = current_player_slot_old;
ALTER TABLE sessions DROP COLUMN current_player_slot_old;

ALTER TABLE turns RENAME COLUMN player_slot TO player_slot_old;
ALTER TABLE turns ADD COLUMN player_slot TEXT
    CHECK (player_slot IS NULL OR player_slot IN ('player_1', 'player_2', 'player_3'));
UPDATE turns SET player_slot = player_slot_old;
ALTER TABLE turns DROP COLUMN player_slot_old;

ALTER TABLE card_feedback RENAME COLUMN player_slot TO player_slot_old;
ALTER TABLE card_feedback ADD COLUMN player_slot TEXT NOT NULL DEFAULT 'player_1'
    CHECK (player_slot IN ('player_1', 'player_2', 'player_3'));
UPDATE card_feedback SET player_slot = player_slot_old;
ALTER TABLE card_feedback DROP COLUMN player_slot_old;

ALTER TABLE users RENAME COLUMN role TO role_old;
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'player_1'
    CHECK (role IN ('player_1', 'player_2', 'player_3'));
UPDATE users SET role = role_old;
ALTER TABLE users DROP COLUMN role_old;

INSERT OR IGNORE INTO content_collections (code, name, description) VALUES
    ('threesome', 'На троих', 'Карточки для игры втроём в группе; включает админ');
