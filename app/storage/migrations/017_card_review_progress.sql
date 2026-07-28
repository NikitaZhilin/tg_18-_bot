CREATE TABLE IF NOT EXISTS card_review_progress (
    admin_user_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    card_version_marker TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('ok', 'needs_revision')
    ),
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (admin_user_id, card_id),
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_card_review_progress_admin
ON card_review_progress(admin_user_id, reviewed_at DESC);
