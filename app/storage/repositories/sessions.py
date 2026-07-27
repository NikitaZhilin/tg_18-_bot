from __future__ import annotations

import sqlite3
from typing import Iterable

from app.storage import Database


class SessionRepository:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def chat_key(chat_id: int, thread_id: int | None = None) -> str:
        return f"{chat_id}:{thread_id or 0}"

    def ensure_chat_context(self, chat_key: str, chat_id: int, thread_id: int | None, title: str | None = None) -> None:
        self.db.execute(
            """
            INSERT INTO chat_contexts (chat_key, telegram_chat_id, telegram_thread_id, title, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_key) DO UPDATE SET
                title = excluded.title,
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (chat_key, chat_id, thread_id, title),
        )

    def get_active(self, chat_key: str, conn: sqlite3.Connection | None = None):
        executor = conn or self.db
        return executor.execute(
            """
            SELECT * FROM sessions
            WHERE chat_key = ? AND status IN ('draft', 'active')
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_key,),
        ).fetchone()

    def create(
        self,
        chat_key: str,
        player_1_id: int,
        player_2_id: int,
        current_player_id: int,
        allow_level_4: bool = False,
        current_player_slot: str = "player_1",
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO sessions (
                chat_key, player_1_id, player_2_id, current_player_id,
                current_player_slot, allow_level_4, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                chat_key,
                player_1_id,
                player_2_id,
                current_player_id,
                current_player_slot,
                1 if allow_level_4 else 0,
            ),
        )
        return int(cur.lastrowid)

    def set_items(self, session_id: int, item_codes: Iterable[str]) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM session_items WHERE session_id = ?", (session_id,))
            for code in item_codes:
                conn.execute(
                    "INSERT OR IGNORE INTO session_items (session_id, item_code) VALUES (?, ?)",
                    (session_id, code),
                )

    def set_blocked_tags(self, session_id: int, tags: Iterable[str]) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM session_blocked_tags WHERE session_id = ?", (session_id,))
            for tag in tags:
                conn.execute(
                    "INSERT OR IGNORE INTO session_blocked_tags (session_id, risk_tag) VALUES (?, ?)",
                    (session_id, tag),
                )

    def add_consent(self, session_id: int, user_id: int, consent_type: str, accepted: bool = True) -> None:
        self.db.execute(
            """
            INSERT INTO session_consents (session_id, user_id, consent_type, accepted)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id, user_id, consent_type) DO UPDATE SET
                accepted = excluded.accepted,
                accepted_at = CURRENT_TIMESTAMP
            """,
            (session_id, user_id, consent_type, 1 if accepted else 0),
        )

    def accepted_count(self, session_id: int, consent_type: str) -> int:
        row = self.db.fetchone(
            """
            SELECT COUNT(*) AS count
            FROM session_consents
            WHERE session_id = ? AND consent_type = ? AND accepted = 1
            """,
            (session_id, consent_type),
        )
        return int(row["count"])

    def set_level_4(self, session_id: int, enabled: bool) -> None:
        self.db.execute(
            "UPDATE sessions SET allow_level_4 = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (1 if enabled else 0, session_id),
        )

    def set_max_intensity(self, session_id: int, intensity: str) -> None:
        self.db.execute(
            "UPDATE sessions SET max_intensity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (intensity, session_id),
        )

    def set_restricted_content(self, session_id: int, enabled: bool) -> None:
        self.db.execute(
            "UPDATE sessions SET allow_restricted_content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (1 if enabled else 0, session_id),
        )

    def finish_session(self, session_id: int, status: str, reason: str | None = None) -> None:
        self.db.execute(
            """
            UPDATE sessions
            SET status = ?, stop_reason = ?, stopped_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, reason, session_id),
        )
