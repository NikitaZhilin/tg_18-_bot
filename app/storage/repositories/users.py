from __future__ import annotations

from app.storage import Database


class UserRepository:
    def __init__(self, db: Database):
        self.db = db

    def upsert_user(self, telegram_id: int, display_name: str, role: str) -> None:
        self.db.execute(
            """
            INSERT INTO users (telegram_id, display_name, role)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                display_name = excluded.display_name,
                role = excluded.role,
                is_active = 1
            """,
            (telegram_id, display_name, role),
        )

    def get(self, telegram_id: int):
        return self.db.fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
