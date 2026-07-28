from __future__ import annotations

import sqlite3

from app.services.errors import GameError
from app.storage import Database
from app.storage.repositories.sessions import SessionRepository


class SessionSettingsMixin:
    db: Database
    sessions: SessionRepository

    def active_session(self, chat_id: int, thread_id: int | None) -> sqlite3.Row | None:
        raise NotImplementedError

    def set_items_for_active_session(
        self,
        chat_id: int,
        thread_id: int | None,
        items: dict[str, int],
    ) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.set_items(int(session["id"]), items)

    def inventory_draft(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
    ) -> dict[str, int]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        session_id = int(session["id"])
        draft = self.sessions.get_setting_draft(session_id, user_id, "inventory")
        if isinstance(draft, dict):
            return {
                str(code): max(1, min(3, int(frequency)))
                for code, frequency in draft.items()
                if int(frequency) > 0
            }
        selected = self.items_for_active_session(chat_id, thread_id)
        self.sessions.set_setting_draft(session_id, user_id, "inventory", selected)
        return selected

    def toggle_inventory_draft(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
        item_code: str,
    ) -> dict[str, int]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        selected = self.inventory_draft(chat_id, thread_id, user_id)
        next_frequency = (int(selected.get(item_code, 0)) + 1) % 4
        if next_frequency:
            selected[item_code] = next_frequency
        else:
            selected.pop(item_code, None)
        self.sessions.set_setting_draft(int(session["id"]), user_id, "inventory", selected)
        return selected

    def save_inventory_draft(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
    ) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        selected = self.inventory_draft(chat_id, thread_id, user_id)
        session_id = int(session["id"])
        self.sessions.set_items(session_id, selected)
        self.sessions.delete_setting_draft(session_id, user_id, "inventory")

    def items_for_active_session(self, chat_id: int, thread_id: int | None) -> dict[str, int]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return {}
        return {
            str(row["item_code"]): int(row["frequency"])
            for row in self.db.fetchall(
                "SELECT item_code, frequency FROM session_items WHERE session_id = ?",
                (session["id"],),
            )
        }

    def available_items(self) -> list[sqlite3.Row]:
        return self.db.fetchall(
            """
            SELECT code, name
            FROM items
            WHERE is_active = 1
              AND is_archived = 0
              AND deleted_at IS NULL
            ORDER BY name
            """
        )

    def enabled_levels(self, chat_id: int, thread_id: int | None) -> tuple[int, ...]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return ()
        return self.sessions.enabled_levels(int(session["id"]))

    def set_enabled_level(
        self,
        chat_id: int,
        thread_id: int | None,
        level: int,
        enabled: bool,
    ) -> tuple[int, ...]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        current = set(self.sessions.enabled_levels(int(session["id"])))
        if enabled:
            current.add(level)
        else:
            current.discard(level)
        if not current:
            raise GameError("Нужно оставить включенным хотя бы один уровень")
        self.sessions.set_enabled_level(int(session["id"]), level, enabled)
        return tuple(sorted(current))

    def set_boundaries_for_active_session(
        self,
        chat_id: int,
        thread_id: int | None,
        risk_tags: list[str],
        user_id: int | None = None,
    ) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.set_blocked_tags(int(session["id"]), risk_tags)
        self.db.execute(
            """
            INSERT INTO safety_events (session_id, user_id, event_type, details)
            VALUES (?, ?, 'boundary_updated', ?)
            """,
            (session["id"], user_id, ",".join(risk_tags)),
        )

    def boundaries_draft(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
    ) -> set[str]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        session_id = int(session["id"])
        draft = self.sessions.get_setting_draft(session_id, user_id, "boundaries")
        if isinstance(draft, list):
            return {str(tag) for tag in draft}
        selected = self.boundaries_for_active_session(chat_id, thread_id)
        self.sessions.set_setting_draft(session_id, user_id, "boundaries", sorted(selected))
        return selected

    def toggle_boundaries_draft(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
        risk_tag: str,
    ) -> set[str]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        selected = self.boundaries_draft(chat_id, thread_id, user_id)
        if risk_tag in selected:
            selected.remove(risk_tag)
        else:
            selected.add(risk_tag)
        self.sessions.set_setting_draft(
            int(session["id"]),
            user_id,
            "boundaries",
            sorted(selected),
        )
        return selected

    def save_boundaries_draft(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
    ) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        selected = self.boundaries_draft(chat_id, thread_id, user_id)
        session_id = int(session["id"])
        self.set_boundaries_for_active_session(
            chat_id,
            thread_id,
            sorted(selected),
            user_id,
        )
        self.sessions.delete_setting_draft(session_id, user_id, "boundaries")

    def boundaries_for_active_session(
        self,
        chat_id: int,
        thread_id: int | None,
    ) -> set[str]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return set()
        return {
            str(row["risk_tag"])
            for row in self.db.fetchall(
                "SELECT risk_tag FROM session_blocked_tags WHERE session_id = ?",
                (session["id"],),
            )
        }
