DROP INDEX IF EXISTS idx_cards_lookup;

ALTER TABLE cards DROP COLUMN requires_both_opt_in;
ALTER TABLE cards DROP COLUMN requires_safeword_check;
ALTER TABLE cards DROP COLUMN safety_level;

CREATE INDEX IF NOT EXISTS idx_cards_lookup
ON cards(level, category, intensity, is_enabled, review_status);
