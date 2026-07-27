from __future__ import annotations

from datetime import UTC, datetime, timedelta

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

    def due(self) -> list:
        now = datetime.now(UTC).isoformat()
        return self.db.fetchall(
            "SELECT * FROM timers WHERE status = 'active' AND deadline_at <= ?",
            (now,),
        )

    def mark_completed(self, timer_id: int) -> None:
        self.db.execute(
            "UPDATE timers SET status = 'completed', notified_at = CURRENT_TIMESTAMP WHERE id = ?",
            (timer_id,),
        )

    def cancel_session_timers(self, session_id: int) -> None:
        self.db.execute(
            "UPDATE timers SET status = 'cancelled' WHERE session_id = ? AND status = 'active'",
            (session_id,),
        )
