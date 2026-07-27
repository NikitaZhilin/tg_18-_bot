PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('player_1', 'player_2')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_contexts (
    chat_key TEXT PRIMARY KEY,
    telegram_chat_id INTEGER NOT NULL,
    telegram_thread_id INTEGER,
    title TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS items (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 4),
    category TEXT NOT NULL CHECK (
        category IN ('question', 'task', 'pose', 'desire', 'penalty')
    ),
    intensity TEXT NOT NULL DEFAULT 'light' CHECK (
        intensity IN ('light', 'medium', 'hard')
    ),
    title TEXT,
    text TEXT NOT NULL,
    media_id TEXT,
    media_file TEXT,
    media_type TEXT CHECK (
        media_type IS NULL OR media_type IN ('photo', 'animation', 'video')
    ),
    pose_family TEXT,
    pose_difficulty TEXT CHECK (
        pose_difficulty IS NULL OR pose_difficulty IN ('easy', 'medium', 'hard')
    ),
    space_required TEXT CHECK (
        space_required IS NULL OR space_required IN ('bed', 'floor', 'chair', 'wall', 'any')
    ),
    body_load TEXT CHECK (
        body_load IS NULL OR body_load IN ('low', 'medium', 'high')
    ),
    avoid_if_tags TEXT NOT NULL DEFAULT '[]',
    source_note TEXT,
    timer_seconds INTEGER CHECK (
        timer_seconds IS NULL OR timer_seconds > 0
    ),
    safety_level TEXT NOT NULL DEFAULT 'normal' CHECK (
        safety_level IN ('normal', 'sensitive', 'hard')
    ),
    risk_tags TEXT NOT NULL DEFAULT '[]',
    requires_both_opt_in INTEGER NOT NULL DEFAULT 0 CHECK (
        requires_both_opt_in IN (0, 1)
    ),
    requires_safeword_check INTEGER NOT NULL DEFAULT 0 CHECK (
        requires_safeword_check IN (0, 1)
    ),
    aftercare_required INTEGER NOT NULL DEFAULT 0 CHECK (
        aftercare_required IN (0, 1)
    ),
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    review_status TEXT NOT NULL DEFAULT 'draft' CHECK (
        review_status IN ('draft', 'needs_review', 'approved', 'disabled')
    ),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS card_required_items (
    card_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    PRIMARY KEY (card_id, item_code),
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    FOREIGN KEY (item_code) REFERENCES items(code) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS content_collections (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS card_collection_items (
    collection_code TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    PRIMARY KEY (collection_code, card_id),
    FOREIGN KEY (collection_code) REFERENCES content_collections(code) ON DELETE CASCADE,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('draft', 'active', 'stopped', 'completed', 'reset')
    ),
    player_1_id INTEGER NOT NULL,
    player_2_id INTEGER NOT NULL,
    current_player_id INTEGER NOT NULL,
    active_turn_id INTEGER,
    safety_preset TEXT NOT NULL DEFAULT 'normal' CHECK (
        safety_preset IN ('normal', 'sensitive', 'hard')
    ),
    allow_level_4 INTEGER NOT NULL DEFAULT 0 CHECK (allow_level_4 IN (0, 1)),
    allow_penalties INTEGER NOT NULL DEFAULT 0 CHECK (allow_penalties IN (0, 1)),
    max_intensity TEXT NOT NULL DEFAULT 'light' CHECK (
        max_intensity IN ('light', 'medium', 'hard')
    ),
    content_version TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    stopped_at TEXT,
    stop_reason TEXT,
    FOREIGN KEY (chat_key) REFERENCES chat_contexts(chat_key),
    FOREIGN KEY (player_1_id) REFERENCES users(telegram_id),
    FOREIGN KEY (player_2_id) REFERENCES users(telegram_id),
    FOREIGN KEY (current_player_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS session_items (
    session_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    PRIMARY KEY (session_id, item_code),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (item_code) REFERENCES items(code) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS session_blocked_tags (
    session_id INTEGER NOT NULL,
    risk_tag TEXT NOT NULL,
    PRIMARY KEY (session_id, risk_tag),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_consents (
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    consent_type TEXT NOT NULL CHECK (
        consent_type IN ('base_game', 'level_4', 'hard_intensity', 'penalties')
    ),
    accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, user_id, consent_type),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    turn_number INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    card_id INTEGER,
    source TEXT NOT NULL CHECK (
        source IN ('manual', 'roulette', 'penalty')
    ),
    status TEXT NOT NULL DEFAULT 'selecting' CHECK (
        status IN ('selecting', 'active', 'completed', 'skipped', 'stopped', 'expired')
    ),
    selected_level INTEGER CHECK (selected_level BETWEEN 1 AND 4),
    selected_category TEXT CHECK (
        selected_category IS NULL
        OR selected_category IN ('question', 'task', 'pose', 'desire', 'penalty')
    ),
    selected_intensity TEXT CHECK (
        selected_intensity IS NULL
        OR selected_intensity IN ('light', 'medium', 'hard')
    ),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    callback_nonce TEXT UNIQUE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES users(telegram_id),
    FOREIGN KEY (card_id) REFERENCES cards(id)
);

CREATE TABLE IF NOT EXISTS used_cards (
    session_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    turn_id INTEGER NOT NULL,
    used_by INTEGER NOT NULL,
    used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, card_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    FOREIGN KEY (turn_id) REFERENCES turns(id) ON DELETE CASCADE,
    FOREIGN KEY (used_by) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS timers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    turn_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    started_by INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deadline_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'completed', 'cancelled', 'expired')
    ),
    notified_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (turn_id) REFERENCES turns(id) ON DELETE CASCADE,
    FOREIGN KEY (card_id) REFERENCES cards(id),
    FOREIGN KEY (started_by) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS saved_desires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    granted_by INTEGER,
    status TEXT NOT NULL DEFAULT 'saved' CHECK (
        status IN ('saved', 'used', 'cancelled')
    ),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    used_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(telegram_id),
    FOREIGN KEY (granted_by) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS safety_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    turn_id INTEGER,
    user_id INTEGER,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'stopword',
            'safe_skip',
            'level_4_enabled',
            'level_4_disabled',
            'hard_enabled',
            'hard_disabled',
            'boundary_updated',
            'aftercare_completed'
        )
    ),
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (turn_id) REFERENCES turns(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS app_heartbeats (
    component TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('ok', 'degraded', 'down')),
    details TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS card_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    changed_by INTEGER,
    change_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (card_id, version_number),
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS admin_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL CHECK (
        action_type IN (
            'create_card',
            'update_card',
            'approve_card',
            'disable_card',
            'duplicate_card',
            'import_cards',
            'export_cards',
            'rollback_card',
            'set_boundary',
            'create_collection',
            'update_collection',
            'disable_collection',
            'delete_draft'
        )
    ),
    target_type TEXT NOT NULL,
    target_id TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_user_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS content_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    content_version TEXT NOT NULL,
    imported_cards INTEGER NOT NULL DEFAULT 0,
    disabled_cards INTEGER NOT NULL DEFAULT 0,
    warnings_count INTEGER NOT NULL DEFAULT 0,
    report_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cards_lookup
ON cards(level, category, intensity, is_enabled, review_status, safety_level);

CREATE INDEX IF NOT EXISTS idx_cards_external_id
ON cards(external_id);

CREATE INDEX IF NOT EXISTS idx_cards_review
ON cards(review_status, category, updated_at);

CREATE INDEX IF NOT EXISTS idx_card_required_items_card
ON card_required_items(card_id);

CREATE INDEX IF NOT EXISTS idx_card_collections_card
ON card_collection_items(card_id);

CREATE INDEX IF NOT EXISTS idx_sessions_chat_status
ON sessions(chat_key, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_turns_session_status
ON turns(session_id, status, turn_number);

CREATE INDEX IF NOT EXISTS idx_used_cards_session
ON used_cards(session_id);

CREATE INDEX IF NOT EXISTS idx_timers_status_deadline
ON timers(status, deadline_at);

CREATE INDEX IF NOT EXISTS idx_admin_actions_created
ON admin_actions(admin_user_id, created_at DESC);

INSERT OR IGNORE INTO items (code, name) VALUES
    ('ice', 'Лед'),
    ('oil', 'Масло'),
    ('rope', 'Веревка'),
    ('blindfold', 'Повязка'),
    ('vibrator', 'Вибратор'),
    ('headphones', 'Наушники'),
    ('candle', 'Свеча'),
    ('clamps', 'Зажимы'),
    ('food', 'Еда');

INSERT OR IGNORE INTO content_collections (code, name, description) VALUES
    ('base_tasks', 'Базовые задания', 'Основной набор заданий уровней 1-4'),
    ('kamasutra_inspired_poses', 'Позы в стиле камасутры', 'Неграфичный каталог поз с уровнем, интенсивностью и ограничениями');
