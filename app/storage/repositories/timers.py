from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.storage import Database


class TimerRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, session_id: int, turn_id: int, card_id: int, started_by: int, duration_seconds: int) -> int:
        deadline = datetime.now(UTC) + timedelta(seconds=duration_seconds)
        cur = self.db.execute(
            """
            INSERT INTO timers (session_id, turn_id, card_id, started_by, duration_seconds, deadline_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, turn_id, card_id, started_by, duration_seconds, deadline.isoformat()),
        )
        return int(cur.lastrowid)

    def active_for_turn(self, turn_id: int):
        return self.db.fetchone(
            "SELECT * FROM timers WHERE turn_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (turn_id,),
        )

    def claim_due(self, *, limit: int = 100, lease_seconds: int = 120) -> list:
        now = datetime.now(UTC)
        now_value = now.isoformat()
        claim_until = (now + timedelta(seconds=lease_seconds)).isoformat()
        claimed = []
        with self.db.transaction() as conn:
            candidates = conn.execute(
                """
                SELECT id
                FROM timers
                WHERE status = 'active'
                  AND deadline_at <= ?
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                  AND (claim_until IS NULL OR claim_until <= ?)
                ORDER BY deadline_at, id
                LIMIT ?
                """,
                (now_value, now_value, now_value, limit),
            ).fetchall()
            for candidate in candidates:
                token = uuid4().hex
                updated = conn.execute(
                    """
                    UPDATE timers
                    SET claim_token = ?,
                        claim_until = ?,
                        attempt_count = attempt_count + 1
                    WHERE id = ?
                      AND status = 'active'
                      AND (claim_until IS NULL OR claim_until <= ?)
                    """,
                    (token, claim_until, candidate["id"], now_value),
                )
                if updated.rowcount:
                    claimed.append(
                        conn.execute(
                            "SELECT * FROM timers WHERE id = ?",
                            (candidate["id"],),
                        ).fetchone()
                    )
        return claimed

    def mark_completed(self, timer_id: int, claim_token: str) -> None:
        self.db.execute(
            """
            UPDATE timers
            SET status = 'completed',
                notified_at = CURRENT_TIMESTAMP,
                claim_token = NULL,
                claim_until = NULL,
                last_error = NULL
            WHERE id = ? AND status = 'active' AND claim_token = ?
            """,
            (timer_id, claim_token),
        )

    def mark_failed(
        self,
        timer_id: int,
        claim_token: str,
        error: str,
        *,
        max_attempts: int = 5,
    ) -> None:
        timer = self.db.fetchone(
            """
            SELECT attempt_count
            FROM timers
            WHERE id = ? AND status = 'active' AND claim_token = ?
            """,
            (timer_id, claim_token),
        )
        if not timer:
            return
        attempt_count = int(timer["attempt_count"])
        if attempt_count >= max_attempts:
            self.db.execute(
                """
                UPDATE timers
                SET status = 'expired',
                    claim_token = NULL,
                    claim_until = NULL,
                    last_error = ?
                WHERE id = ? AND claim_token = ?
                """,
                (error[:1000], timer_id, claim_token),
            )
            return
        delay_seconds = min(300, 5 * (2 ** (attempt_count - 1)))
        next_attempt = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        self.db.execute(
            """
            UPDATE timers
            SET next_attempt_at = ?,
                claim_token = NULL,
                claim_until = NULL,
                last_error = ?
            WHERE id = ? AND status = 'active' AND claim_token = ?
            """,
            (next_attempt.isoformat(), error[:1000], timer_id, claim_token),
        )

    def cancel_session_timers(self, session_id: int) -> None:
        self.db.execute(
            """
            UPDATE timers
            SET status = 'cancelled', claim_token = NULL, claim_until = NULL
            WHERE session_id = ? AND status = 'active'
            """,
            (session_id,),
        )
