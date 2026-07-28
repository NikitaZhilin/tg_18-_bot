CREATE TABLE IF NOT EXISTS daily_consents (
    chat_key TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    consent_date TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_key, user_id, consent_date),
    FOREIGN KEY (chat_key) REFERENCES chat_contexts(chat_key) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_daily_consents_lookup
ON daily_consents(chat_key, consent_date, user_id);
