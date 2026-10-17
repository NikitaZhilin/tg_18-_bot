-- «⭐ Избранное»: cards a chat liked and wants to play again.
CREATE TABLE IF NOT EXISTS favorite_cards (
    chat_key TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_key, card_id)
);
