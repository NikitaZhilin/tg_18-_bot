from __future__ import annotations

from app.storage import Database
from app.storage.repositories.sessions import SessionRepository
from app.storage.repositories.timers import TimerRepository


class SafetyService:
    def __init__(self, db: Database):
        self.db = db
        self.sessions = SessionRepository(db)
        self.timers = TimerRepository(db)

    def stopword(self, chat_id: int, thread_id: int | None, user_id: int | None) -> bool:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session:
                return False
            conn.execute(
                """
                UPDATE turns
                SET status = 'stopped', finished_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND status IN ('selecting', 'active')
                """,
                (session["id"],),
            )
            conn.execute(
                """
                UPDATE timers
                SET status = 'cancelled', claim_token = NULL, claim_until = NULL
                WHERE session_id = ? AND status = 'active'
                """,
                (session["id"],),
            )
            conn.execute(
                """
                UPDATE sessions
                SET status = 'stopped',
                    stop_reason = 'stopword',
                    stopped_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (session["id"],),
            )
            conn.execute(
                """
                INSERT INTO safety_events (session_id, turn_id, user_id, event_type)
                VALUES (?, ?, ?, 'stopword')
                """,
                (session["id"], session["active_turn_id"], user_id),
            )
            return True

    def safe_skip(self, session_id: int, turn_id: int | None, user_id: int) -> None:
        self.db.execute(
            """
            INSERT INTO safety_events (session_id, turn_id, user_id, event_type)
            VALUES (?, ?, ?, 'safe_skip')
            """,
            (session_id, turn_id, user_id),
        )
