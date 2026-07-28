UPDATE saved_desires
SET owner_slot = CASE
        WHEN (
            SELECT player_1_id <> player_2_id
            FROM sessions
            WHERE sessions.id = saved_desires.session_id
        )
        THEN CASE
            WHEN owner_id = (
                SELECT player_2_id
                FROM sessions
                WHERE sessions.id = saved_desires.session_id
            )
            THEN 'player_2'
            ELSE 'player_1'
        END
        ELSE owner_slot
    END,
    granted_by_slot = CASE
        WHEN (
            SELECT player_1_id <> player_2_id
            FROM sessions
            WHERE sessions.id = saved_desires.session_id
        )
        THEN CASE
            WHEN granted_by = (
                SELECT player_2_id
                FROM sessions
                WHERE sessions.id = saved_desires.session_id
            )
            THEN 'player_2'
            ELSE 'player_1'
        END
        ELSE granted_by_slot
    END;

DROP TABLE IF EXISTS daily_consents;

ALTER TABLE sessions DROP COLUMN allow_level_4;
ALTER TABLE sessions DROP COLUMN max_intensity;
