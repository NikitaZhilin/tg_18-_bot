"""Groups open with a password; players join with «Я играю».

The password itself never lives in the repository: an admin types it once in the
bot, and only a PBKDF2 hash is stored in bot_settings.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.storage import Database

PASSWORD_KEY = "group_password"
ITERATIONS = 300_000


def _hash(password: str, salt: bytes, iterations: int = ITERATIONS) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.strip().encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


class GroupAccess:
    def __init__(self, db: Database):
        self.db = db

    # --- password -----------------------------------------------------------
    def _stored(self) -> str | None:
        try:
            row = self.db.fetchone("SELECT value FROM bot_settings WHERE key = ?", (PASSWORD_KEY,))
        except Exception:
            return None
        return str(row["value"]) if row and row["value"] else None

    def has_password(self) -> bool:
        return self._stored() is not None

    def set_password(self, password: str, user_id: int | None = None) -> None:
        self.db.execute(
            """
            INSERT INTO bot_settings (key, value, updated_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP
            """,
            (PASSWORD_KEY, _hash(password, secrets.token_bytes(16)), user_id),
        )

    def check_password(self, password: str) -> bool:
        stored = self._stored()
        if not stored or not password:
            return False
        try:
            _, iterations, salt_hex, _ = stored.split("$")
            expected = _hash(password, bytes.fromhex(salt_hex), int(iterations))
        except ValueError:
            return False
        return hmac.compare_digest(expected, stored)

    # --- groups -------------------------------------------------------------
    def is_unlocked(self, chat_id: int) -> bool:
        try:
            return self.db.fetchone("SELECT 1 FROM unlocked_groups WHERE telegram_chat_id = ?", (chat_id,)) is not None
        except Exception:
            return False

    def unlock(self, chat_id: int, user_id: int | None) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO unlocked_groups (telegram_chat_id, unlocked_by) VALUES (?, ?)",
            (chat_id, user_id),
        )

    # --- roster -------------------------------------------------------------
    def roster(self, chat_id: int) -> list[tuple[int, str]]:
        try:
            rows = self.db.fetchall(
                "SELECT user_id, display_name FROM group_players WHERE telegram_chat_id = ? ORDER BY position",
                (chat_id,),
            )
        except Exception:
            return []
        return [(int(r["user_id"]), str(r["display_name"])) for r in rows]

    def in_roster(self, chat_id: int, user_id: int) -> bool:
        return any(uid == int(user_id) for uid, _ in self.roster(chat_id))

    def join(self, chat_id: int, user_id: int, name: str, limit: int) -> bool:
        """Adds a player; False when the game is already full."""
        roster = self.roster(chat_id)
        if any(uid == int(user_id) for uid, _ in roster):
            return True
        if len(roster) >= limit:
            return False
        self.db.execute(
            "INSERT INTO group_players (telegram_chat_id, user_id, display_name, position) VALUES (?, ?, ?, ?)",
            (chat_id, int(user_id), (name or "Игрок").strip()[:32], len(roster) + 1),
        )
        return True

    def clear_roster(self, chat_id: int) -> None:
        try:
            self.db.execute("DELETE FROM group_players WHERE telegram_chat_id = ?", (chat_id,))
        except Exception:
            pass

    def name_of(self, chat_id: int, user_id: int) -> str | None:
        for uid, name in self.roster(chat_id):
            if uid == int(user_id):
                return name
        return None


registry: GroupAccess | None = None
