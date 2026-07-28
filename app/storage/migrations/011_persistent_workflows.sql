CREATE TABLE IF NOT EXISTS fsm_states (
    bot_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL DEFAULT 0,
    business_connection_id TEXT NOT NULL DEFAULT '',
    destiny TEXT NOT NULL DEFAULT 'default',
    state TEXT,
    data_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        bot_id,
        chat_id,
        user_id,
        thread_id,
        business_connection_id,
        destiny
    )
);

CREATE TABLE IF NOT EXISTS session_setting_drafts (
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    draft_type TEXT NOT NULL CHECK (draft_type IN ('inventory', 'boundaries')),
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, user_id, draft_type),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
