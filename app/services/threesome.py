"""Hidden «игра на троих»: an admin turns it on and names the third player.

It works only in a group: the couple plus the third, each from their own phone.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.storage import Database

ENABLED_KEY = "threesome_enabled"
THIRD_ID_KEY = "threesome_third_id"
THIRD_NAME_KEY = "threesome_third_name"


@dataclass(frozen=True)
class ThreesomeState:
    enabled: bool
    third_id: int | None
    third_name: str

    @property
    def active(self) -> bool:
        return self.enabled


class ThreesomeSettings:
    def __init__(self, db: Database):
        self.db = db

    def _get(self, key: str) -> str | None:
        try:
            row = self.db.fetchone("SELECT value FROM bot_settings WHERE key = ?", (key,))
        except Exception:
            return None  # database from before migration 024
        return str(row["value"]) if row and row["value"] is not None else None

    def _set(self, key: str, value: str | None, user_id: int | None) -> None:
        self.db.execute(
            """
            INSERT INTO bot_settings (key, value, updated_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_by = excluded.updated_by,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value, user_id),
        )

    def state(self) -> ThreesomeState:
        third = self._get(THIRD_ID_KEY)
        return ThreesomeState(
            enabled=self._get(ENABLED_KEY) == "1",
            third_id=int(third) if third and third.lstrip("-").isdigit() else None,
            third_name=self._get(THIRD_NAME_KEY) or "Гостья",
        )

    def set_enabled(self, enabled: bool, user_id: int | None = None) -> None:
        self._set(ENABLED_KEY, "1" if enabled else "0", user_id)

    def set_third(self, third_id: int, name: str, user_id: int | None = None) -> None:
        self._set(THIRD_ID_KEY, str(int(third_id)), user_id)
        self._set(THIRD_NAME_KEY, name.strip()[:32] or "Гостья", user_id)

    def clear_third(self, user_id: int | None = None) -> None:
        self._set(THIRD_ID_KEY, None, user_id)

    def is_guest(self, user_id: int, chat) -> bool:
        """The third player may play only inside a group, never in private chats."""
        if getattr(chat, "type", None) not in ("group", "supergroup"):
            return False
        state = self.state()
        return state.active and state.third_id == int(user_id)


# Set by build_dispatcher so that access checks can see the third player.
registry: ThreesomeSettings | None = None
