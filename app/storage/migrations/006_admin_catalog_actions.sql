ALTER TABLE admin_actions RENAME TO admin_actions_before_catalog;

CREATE TABLE admin_actions (
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
            'delete_draft',
            'archive_card',
            'restore_card',
            'delete_card',
            'create_item',
            'update_item',
            'archive_item',
            'restore_item',
            'delete_item'
        )
    ),
    target_type TEXT NOT NULL,
    target_id TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_user_id) REFERENCES users(telegram_id)
);

INSERT INTO admin_actions (
    id, admin_user_id, action_type, target_type, target_id, details_json, created_at
)
SELECT
    id, admin_user_id, action_type, target_type, target_id, details_json, created_at
FROM admin_actions_before_catalog;

DROP TABLE admin_actions_before_catalog;

CREATE INDEX IF NOT EXISTS idx_admin_actions_created
ON admin_actions(admin_user_id, created_at DESC);
