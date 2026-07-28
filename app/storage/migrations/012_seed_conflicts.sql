CREATE TABLE IF NOT EXISTS seed_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    external_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    content_version TEXT NOT NULL,
    incoming_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'keep_local', 'apply_seed')),
    resolved_by INTEGER,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (card_id, content_version),
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_by) REFERENCES users(telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_seed_conflicts_status
ON seed_conflicts(status, created_at DESC);
