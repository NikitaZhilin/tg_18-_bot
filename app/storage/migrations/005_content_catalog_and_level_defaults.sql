ALTER TABLE cards ADD COLUMN item_mode TEXT NOT NULL DEFAULT 'none'
CHECK (item_mode IN ('none', 'optional', 'required'));

ALTER TABLE cards ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0
CHECK (is_archived IN (0, 1));

ALTER TABLE cards ADD COLUMN deleted_at TEXT;

ALTER TABLE items ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0
CHECK (is_archived IN (0, 1));

ALTER TABLE items ADD COLUMN deleted_at TEXT;

ALTER TABLE turns ADD COLUMN selected_collection_code TEXT;

CREATE TABLE IF NOT EXISTS session_enabled_levels (
    session_id INTEGER NOT NULL,
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 4),
    PRIMARY KEY (session_id, level),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

INSERT OR IGNORE INTO session_enabled_levels (session_id, level)
SELECT id, 1 FROM sessions;

INSERT OR IGNORE INTO session_enabled_levels (session_id, level)
SELECT id, 2 FROM sessions;

INSERT OR IGNORE INTO session_enabled_levels (session_id, level)
SELECT id, 3 FROM sessions;

UPDATE content_collections
SET name = 'Экстрим',
    description = 'Самая интенсивная отдельная коллекция. Доступна только после админского пароля и подтверждений уровня BDSM и жесткой интенсивности.'
WHERE code = 'restricted_content';

CREATE INDEX IF NOT EXISTS idx_cards_catalog
ON cards(level, category, is_archived, deleted_at, updated_at);

CREATE INDEX IF NOT EXISTS idx_items_catalog
ON items(is_archived, deleted_at, name);
