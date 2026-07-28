from __future__ import annotations

import sqlite3

from app.config import Config
from app.storage import Database
from app.storage.repositories.sessions import SessionRepository


class DesireError(RuntimeError):
    pass


class DesireService:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config
        self.sessions = SessionRepository(db)

    def _active_session(self, chat_id: int, thread_id: int | None) -> sqlite3.Row:
        session = self.sessions.get_active(self.sessions.chat_key(chat_id, thread_id))
        if not session:
            raise DesireError("Нет активной сессии")
        return session

    def player_label(self, slot: str) -> str:
        return self.config.player_2_name if slot == "player_2" else self.config.player_1_name

    def list_saved(
        self,
        chat_id: int,
        thread_id: int | None,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        session = self._active_session(chat_id, thread_id)
        return self.db.fetchall(
            """
            SELECT
                sd.*,
                c.title,
                c.text,
                c.level,
                c.intensity
            FROM saved_desires sd
            JOIN cards c ON c.id = sd.card_id
            WHERE sd.session_id = ? AND sd.status = 'saved'
            ORDER BY sd.created_at DESC, sd.id DESC
            LIMIT ? OFFSET ?
            """,
            (session["id"], limit, offset),
        )

    def count_saved(self, chat_id: int, thread_id: int | None) -> int:
        session = self._active_session(chat_id, thread_id)
        row = self.db.fetchone(
            "SELECT COUNT(*) AS count FROM saved_desires WHERE session_id = ? AND status = 'saved'",
            (session["id"],),
        )
        return int(row["count"])

    def get_saved(self, chat_id: int, thread_id: int | None, desire_id: int) -> sqlite3.Row | None:
        session = self._active_session(chat_id, thread_id)
        return self.db.fetchone(
            """
            SELECT sd.*, c.title, c.text, c.level, c.intensity
            FROM saved_desires sd
            JOIN cards c ON c.id = sd.card_id
            WHERE sd.id = ? AND sd.session_id = ? AND sd.status = 'saved'
            """,
            (desire_id, session["id"]),
        )

    def use_saved(
        self,
        chat_id: int,
        thread_id: int | None,
        desire_id: int,
        user_id: int,
    ) -> sqlite3.Row:
        with self.db.transaction() as conn:
            session = self.sessions.get_active(self.sessions.chat_key(chat_id, thread_id), conn)
            if not session:
                raise DesireError("Нет активной сессии")
            desire = conn.execute(
                """
                SELECT sd.*, c.title, c.text, c.level, c.intensity
                FROM saved_desires sd
                JOIN cards c ON c.id = sd.card_id
                WHERE sd.id = ? AND sd.session_id = ? AND sd.status = 'saved'
                """,
                (desire_id, session["id"]),
            ).fetchone()
            if not desire:
                raise DesireError("Желание уже использовано или не найдено")
            if session["active_turn_id"]:
                raise DesireError("Сначала завершите текущую карточку")
            if int(desire["owner_id"]) != int(user_id):
                raise DesireError("Это желание принадлежит другому игроку")
            if str(session["current_player_slot"]) != str(desire["owner_slot"]):
                raise DesireError(
                    f"Это желание сможет использовать {self.player_label(str(desire['owner_slot']))} в свой ход"
                )
            conn.execute(
                """
                UPDATE saved_desires
                SET status = 'used', used_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'saved'
                """,
                (desire_id,),
            )
            return desire
