from __future__ import annotations

from app.storage import Database
from app.storage.repositories.cards import CardRepository
from app.storage.repositories.sessions import SessionRepository


class FeedbackError(RuntimeError):
    pass


class FeedbackService:
    def __init__(self, db: Database):
        self.db = db
        self.sessions = SessionRepository(db)
        self.cards = CardRepository(db)

    def report_unclear(
        self,
        chat_id: int,
        thread_id: int | None,
        turn_id: int,
        user_id: int,
    ) -> bool:
        row = self.db.fetchone(
            """
            SELECT
                t.id AS turn_id,
                t.card_id,
                t.session_id,
                t.player_slot,
                s.player_1_id,
                s.player_2_id
            FROM turns t
            JOIN sessions s ON s.id = t.session_id
            WHERE t.id = ? AND s.chat_key = ? AND t.card_id IS NOT NULL
            """,
            (turn_id, self.sessions.chat_key(chat_id, thread_id)),
        )
        if not row:
            raise FeedbackError("Карточка этого хода не найдена")
        participants = {int(row["player_1_id"]), int(row["player_2_id"])}
        if int(user_id) not in participants:
            raise FeedbackError("Отправить карточку на доработку может только участник игры")
        with self.db.transaction() as conn:
            inserted = conn.execute(
                """
                INSERT OR IGNORE INTO card_feedback (
                    card_id, session_id, turn_id, reported_by, player_slot
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["card_id"],
                    row["session_id"],
                    row["turn_id"],
                    user_id,
                    row["player_slot"],
                ),
            )
            if inserted.rowcount > 0:
                self.cards.save_version(
                    int(row["card_id"]),
                    user_id,
                    "player_requested_revision",
                    conn,
                )
                self.cards.set_status(int(row["card_id"]), "needs_review", False, conn)
            return inserted.rowcount > 0
