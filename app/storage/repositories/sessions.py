from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

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
        current_player_slot: str = "player_1",
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO sessions (
                chat_key, player_1_id, player_2_id, current_player_id,
                current_player_slot, updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                chat_key,
                player_1_id,
                player_2_id,
                current_player_id,
                current_player_slot,
            ),
        )
        session_id = int(cur.lastrowid)
        self.db.executemany(
            "INSERT OR IGNORE INTO session_enabled_levels (session_id, level) VALUES (?, ?)",
            [(session_id, 1), (session_id, 2), (session_id, 3), (session_id, 4)],
        )
        return session_id

    def set_items(self, session_id: int, items: dict[str, int]) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM session_items WHERE session_id = ?", (session_id,))
            for code, frequency in items.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO session_items (session_id, item_code, frequency)
                    VALUES (?, ?, ?)
                    """,
                    (session_id, code, max(1, min(3, int(frequency)))),
                )

    def get_setting_draft(
        self,
        session_id: int,
        user_id: int,
        draft_type: str,
    ) -> dict[str, Any] | list[Any] | None:
        row = self.db.fetchone(
            """
            SELECT data_json
            FROM session_setting_drafts
            WHERE session_id = ? AND user_id = ? AND draft_type = ?
            """,
            (session_id, user_id, draft_type),
        )
        if not row:
            return None
        data = json.loads(str(row["data_json"]))
        return data if isinstance(data, (dict, list)) else None

    def set_setting_draft(
        self,
        session_id: int,
        user_id: int,
        draft_type: str,
        data: dict[str, Any] | list[Any],
    ) -> None:
        self.db.execute(
            """
            INSERT INTO session_setting_drafts (
                session_id, user_id, draft_type, data_json
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id, user_id, draft_type) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                user_id,
                draft_type,
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            ),
        )

    def delete_setting_draft(self, session_id: int, user_id: int, draft_type: str) -> None:
        self.db.execute(
            """
            DELETE FROM session_setting_drafts
            WHERE session_id = ? AND user_id = ? AND draft_type = ?
            """,
            (session_id, user_id, draft_type),
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

    def add_daily_slot_consent(
        self,
        chat_key: str,
        player_slot: str,
        user_id: int,
        consent_date: str,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO daily_slot_consents (
                chat_key, player_slot, user_id, consent_date
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_key, player_slot, consent_date) DO UPDATE SET
                user_id = excluded.user_id,
                accepted_at = CURRENT_TIMESTAMP
            """,
            (chat_key, player_slot, user_id, consent_date),
        )

    def daily_slot_consents(self, chat_key: str, consent_date: str) -> list[sqlite3.Row]:
        return self.db.fetchall(
            """
            SELECT player_slot, user_id
            FROM daily_slot_consents
            WHERE chat_key = ? AND consent_date = ?
            ORDER BY player_slot
            """,
            (chat_key, consent_date),
        )

    def accepted_consent_slots(self, session_id: int) -> set[str]:
        rows = self.db.fetchall(
            """
            SELECT consent_type
            FROM session_consents
            WHERE session_id = ?
              AND consent_type IN ('base_game:player_1', 'base_game:player_2')
              AND accepted = 1
            """,
            (session_id,),
        )
        return {
            str(row["consent_type"]).split(":", 1)[1]
            for row in rows
        }

    def set_restricted_content(self, session_id: int, enabled: bool) -> None:
        self.db.execute(
            "UPDATE sessions SET allow_restricted_content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (1 if enabled else 0, session_id),
        )

    def enabled_levels(self, session_id: int) -> tuple[int, ...]:
        rows = self.db.fetchall(
            """
            SELECT level
            FROM session_enabled_levels
            WHERE session_id = ?
            ORDER BY level
            """,
            (session_id,),
        )
        return tuple(int(row["level"]) for row in rows)

    def set_enabled_level(self, session_id: int, level: int, enabled: bool) -> None:
        if enabled:
            self.db.execute(
                "INSERT OR IGNORE INTO session_enabled_levels (session_id, level) VALUES (?, ?)",
                (session_id, level),
            )
            return
        self.db.execute(
            "DELETE FROM session_enabled_levels WHERE session_id = ? AND level = ?",
            (session_id, level),
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
