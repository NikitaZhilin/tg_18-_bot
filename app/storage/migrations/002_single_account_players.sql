ALTER TABLE sessions ADD COLUMN current_player_slot TEXT NOT NULL DEFAULT 'player_1'
CHECK (current_player_slot IN ('player_1', 'player_2'));

ALTER TABLE turns ADD COLUMN player_slot TEXT CHECK (
    player_slot IS NULL OR player_slot IN ('player_1', 'player_2')
);
