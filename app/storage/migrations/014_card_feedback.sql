CREATE TABLE IF NOT EXISTS card_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    turn_id INTEGER NOT NULL,
    reported_by INTEGER NOT NULL,
    player_slot TEXT NOT NULL CHECK (player_slot IN ('player_1', 'player_2')),
    reason TEXT NOT NULL DEFAULT 'unclear' CHECK (reason IN ('unclear')),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'resolved')),
    resolved_by INTEGER,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (turn_id, reported_by, reason),
    FOREIGN KEY (card_id) REFERENCES cards(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (turn_id) REFERENCES turns(id) ON DELETE CASCADE,
    FOREIGN KEY (reported_by) REFERENCES users(telegram_id),
    FOREIGN KEY (resolved_by) REFERENCES users(telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_card_feedback_status
ON card_feedback(status, created_at DESC);
