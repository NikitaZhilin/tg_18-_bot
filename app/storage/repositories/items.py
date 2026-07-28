from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime

from app.storage import Database


class ItemRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, code: str, conn: sqlite3.Connection | None = None) -> sqlite3.Row | None:
        executor = conn or self.db
        return executor.execute("SELECT * FROM items WHERE code = ?", (code,)).fetchone()

    def list_items(
        self,
        *,
        include_archived: bool = True,
        limit: int = 10,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        where = ["deleted_at IS NULL"]
        if not include_archived:
            where.append("is_archived = 0")
        return self.db.fetchall(
            f"""
            SELECT *
            FROM items
            WHERE {' AND '.join(where)}
            ORDER BY is_archived, name
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )

    def count(self, *, include_archived: bool = True) -> int:
        where = "deleted_at IS NULL" if include_archived else "deleted_at IS NULL AND is_archived = 0"
        row = self.db.fetchone(f"SELECT COUNT(*) AS count FROM items WHERE {where}")
        return int(row["count"])

    def create(
        self,
        *,
        name: str,
        min_level: int,
        max_level: int,
        categories: list[str],
        usage_text: str,
        randomizable: bool,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        executor = conn or self.db
        code = self._unique_code(name, executor)
        executor.execute(
            """
            INSERT INTO items (
                code, name, min_level, max_level, categories, usage_text,
                randomizable, is_active, is_archived
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
            """,
            (
                code,
                name.strip(),
                min_level,
                max_level,
                ",".join(categories),
                usage_text.strip(),
                1 if randomizable else 0,
            ),
        )
        return code

    def update(
        self,
        code: str,
        *,
        name: str | None = None,
        usage_text: str | None = None,
        min_level: int | None = None,
        max_level: int | None = None,
        categories: list[str] | None = None,
        randomizable: bool | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        assignments: list[str] = []
        values: list[object] = []
        for field, value in (
            ("name", name.strip() if name is not None else None),
            ("usage_text", usage_text.strip() if usage_text is not None else None),
            ("min_level", min_level),
            ("max_level", max_level),
            ("categories", ",".join(categories) if categories is not None else None),
            ("randomizable", 1 if randomizable else 0 if randomizable is not None else None),
        ):
            if value is not None:
                assignments.append(f"{field} = ?")
                values.append(value)
        if not assignments:
            return
        values.append(code)
        (conn or self.db).execute(
            f"UPDATE items SET {', '.join(assignments)} WHERE code = ? AND deleted_at IS NULL",
            values,
        )

    def set_archived(
        self,
        code: str,
        archived: bool,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        (conn or self.db).execute(
            """
            UPDATE items
            SET is_archived = ?, is_active = ?
            WHERE code = ? AND deleted_at IS NULL
            """,
            (1 if archived else 0, 0 if archived else 1, code),
        )

    def soft_delete(self, code: str, conn: sqlite3.Connection | None = None) -> None:
        (conn or self.db).execute(
            """
            UPDATE items
            SET deleted_at = CURRENT_TIMESTAMP, is_archived = 1, is_active = 0
            WHERE code = ?
            """,
            (code,),
        )

    def reference_count(self, code: str) -> int:
        row = self.db.fetchone(
            """
            SELECT
                (SELECT COUNT(*) FROM card_required_items WHERE item_code = ?)
              + (SELECT COUNT(*) FROM session_items WHERE item_code = ?) AS count
            """,
            (code, code),
        )
        return int(row["count"])

    def upsert_from_import(
        self,
        data: dict[str, object],
        conn: sqlite3.Connection | None = None,
    ) -> str:
        executor = conn or self.db
        code = str(data.get("code") or "").strip()
        if not code:
            code = self._unique_code(str(data.get("name") or "item"), executor)
        executor.execute(
            """
            INSERT INTO items (
                code, name, min_level, max_level, categories, usage_text,
                randomizable, is_active, is_archived, deleted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                min_level = excluded.min_level,
                max_level = excluded.max_level,
                categories = excluded.categories,
                usage_text = excluded.usage_text,
                randomizable = excluded.randomizable,
                is_active = excluded.is_active,
                is_archived = excluded.is_archived,
                deleted_at = NULL
            """,
            (
                code,
                str(data["name"]).strip(),
                int(data.get("min_level") or 1),
                int(data.get("max_level") or 4),
                str(data.get("categories") or "task,pose,desire"),
                str(data.get("usage_text") or "").strip(),
                int(data.get("randomizable") or 0),
                0 if int(data.get("is_archived") or 0) else 1,
                int(data.get("is_archived") or 0),
            ),
        )
        return code

    @staticmethod
    def _unique_code(name: str, executor: sqlite3.Connection | Database) -> str:
        transliterated = (
            name.casefold()
            .replace(" ", "_")
            .replace("ё", "e")
        )
        base = re.sub(r"[^a-z0-9_]+", "", transliterated).strip("_")
        if not base:
            base = "custom"
        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        candidate = f"{base[:24]}_{suffix}"
        counter = 1
        while executor.execute("SELECT 1 FROM items WHERE code = ?", (candidate,)).fetchone():
            candidate = f"{base[:20]}_{suffix}_{counter}"
            counter += 1
        return candidate
