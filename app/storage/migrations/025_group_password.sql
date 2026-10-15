-- No toy notes under cards at all.
UPDATE items SET usage_text = '' WHERE code IN ('estim', 'gag', 'rope', 'sterile_urethral_kit');

-- Groups open with a password (set by an admin; stored as a hash in bot_settings).
CREATE TABLE IF NOT EXISTS unlocked_groups (
    telegram_chat_id INTEGER PRIMARY KEY,
    unlocked_by INTEGER,
    unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Who plays in a group: whoever pressed «Я играю», in that order.
CREATE TABLE IF NOT EXISTS group_players (
    telegram_chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    position INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (telegram_chat_id, user_id)
);

-- «Экстрим» is always available now.
UPDATE sessions SET allow_restricted_content = 1 WHERE status IN ('draft', 'active');
