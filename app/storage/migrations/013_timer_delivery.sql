ALTER TABLE timers ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE timers ADD COLUMN next_attempt_at TEXT;
ALTER TABLE timers ADD COLUMN claim_token TEXT;
ALTER TABLE timers ADD COLUMN claim_until TEXT;
ALTER TABLE timers ADD COLUMN last_error TEXT;

CREATE INDEX IF NOT EXISTS idx_timers_retry
ON timers(status, next_attempt_at, claim_until);
