ALTER TABLE saved_desires ADD COLUMN owner_slot TEXT NOT NULL DEFAULT 'player_1'
CHECK (owner_slot IN ('player_1', 'player_2'));

ALTER TABLE saved_desires ADD COLUMN granted_by_slot TEXT NOT NULL DEFAULT 'player_2'
CHECK (granted_by_slot IN ('player_1', 'player_2'));

CREATE INDEX IF NOT EXISTS idx_saved_desires_session_status
ON saved_desires(session_id, status, created_at);
