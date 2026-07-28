CREATE TABLE IF NOT EXISTS daily_slot_consents (
    chat_key TEXT NOT NULL,
    player_slot TEXT NOT NULL CHECK (player_slot IN ('player_1', 'player_2')),
    user_id INTEGER NOT NULL,
    consent_date TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_key, player_slot, consent_date),
    FOREIGN KEY (chat_key) REFERENCES chat_contexts(chat_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_daily_slot_consents_date
ON daily_slot_consents(chat_key, consent_date);

CREATE TABLE session_consents_with_slots (
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    consent_type TEXT NOT NULL CHECK (
        consent_type IN (
            'base_game',
            'base_game:player_1',
            'base_game:player_2',
            'level_4',
            'hard_intensity',
            'penalties'
        )
    ),
    accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, user_id, consent_type),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

INSERT INTO session_consents_with_slots (
    session_id, user_id, consent_type, accepted, accepted_at
)
SELECT session_id, user_id, consent_type, accepted, accepted_at
FROM session_consents;

DROP TABLE session_consents;
ALTER TABLE session_consents_with_slots RENAME TO session_consents;
