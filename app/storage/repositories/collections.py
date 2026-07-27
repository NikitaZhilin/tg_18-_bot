from __future__ import annotations

from app.storage import Database


class CollectionRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_enabled(self):
        return self.db.fetchall(
            "SELECT * FROM content_collections WHERE is_enabled = 1 ORDER BY code"
        )

    def upsert(self, code: str, name: str, description: str | None = None) -> None:
        self.db.execute(
            """
            INSERT INTO content_collections (code, name, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                updated_at = CURRENT_TIMESTAMP
            """,
            (code, name, description),
        )
