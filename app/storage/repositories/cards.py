from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.domain import dump_json_list, parse_json_list
from app.storage import Database


CARD_COLUMNS = [
    "external_id",
    "level",
    "category",
    "intensity",
    "title",
    "text",
    "media_id",
    "media_file",
    "media_type",
    "pose_family",
    "pose_difficulty",
    "space_required",
    "body_load",
    "avoid_if_tags",
    "source_note",
    "timer_seconds",
    "risk_tags",
    "aftercare_required",
    "item_mode",
    "is_enabled",
    "review_status",
    "notes",
]


class CardRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, card_id: int, conn: sqlite3.Connection | None = None) -> sqlite3.Row | None:
        executor = conn or self.db
        return executor.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    def get_by_external_id(self, external_id: str, conn: sqlite3.Connection | None = None) -> sqlite3.Row | None:
        executor = conn or self.db
        return executor.execute("SELECT * FROM cards WHERE external_id = ?", (external_id,)).fetchone()

    def upsert(
        self,
        data: dict[str, Any],
        required_items: list[str] | None = None,
        collections: list[str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        executor = conn or self.db
        clean = self._clean_card_data(data)
        external_id = clean.get("external_id")
        existing = self.get_by_external_id(str(external_id), conn) if external_id else None
        if existing:
            assignments = ", ".join(f"{col} = ?" for col in CARD_COLUMNS if col != "external_id")
            values = [clean.get(col) for col in CARD_COLUMNS if col != "external_id"]
            values.append(existing["id"])
            executor.execute(f"UPDATE cards SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
            card_id = int(existing["id"])
        else:
            cols = ", ".join(CARD_COLUMNS)
            placeholders = ", ".join("?" for _ in CARD_COLUMNS)
            values = [clean.get(col) for col in CARD_COLUMNS]
            cur = executor.execute(f"INSERT INTO cards ({cols}) VALUES ({placeholders})", values)
            card_id = int(cur.lastrowid)

        self.replace_required_items(card_id, required_items or [], conn)
        self.replace_collections(card_id, collections or [], conn)
        return card_id

    def replace_required_items(
        self,
        card_id: int,
        required_items: list[str],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        executor = conn or self.db
        executor.execute("DELETE FROM card_required_items WHERE card_id = ?", (card_id,))
        for item in required_items:
            executor.execute(
                "INSERT OR IGNORE INTO card_required_items (card_id, item_code) VALUES (?, ?)",
                (card_id, item),
            )

    def replace_collections(
        self,
        card_id: int,
        collections: list[str],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        executor = conn or self.db
        executor.execute("DELETE FROM card_collection_items WHERE card_id = ?", (card_id,))
        for code in collections:
            executor.execute(
                "INSERT OR IGNORE INTO content_collections (code, name) VALUES (?, ?)",
                (code, code),
            )
            executor.execute(
                "INSERT OR IGNORE INTO card_collection_items (collection_code, card_id) VALUES (?, ?)",
                (code, card_id),
            )

    def list_cards(
        self,
        *,
        review_status: str | None = None,
        level: int | None = None,
        category: str | None = None,
        collection_code: str | None = None,
        include_archived: bool = False,
        limit: int = 10,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        where: list[str] = ["deleted_at IS NULL"]
        params: list[object] = []
        if not include_archived:
            where.append("is_archived = 0")
        if review_status:
            where.append("review_status = ?")
            params.append(review_status)
        if level is not None:
            where.append("level = ?")
            params.append(level)
        if category:
            where.append("category = ?")
            params.append(category)
        if collection_code:
            where.append(
                "EXISTS (SELECT 1 FROM card_collection_items cci "
                "WHERE cci.card_id = cards.id AND cci.collection_code = ?)"
            )
            params.append(collection_code)
        clause = "WHERE " + " AND ".join(where) if where else ""
        params.extend([limit, offset])
        return self.db.fetchall(
            f"""
            SELECT * FROM cards
            {clause}
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            params,
        )

    def search(self, query: str, limit: int = 10) -> list[sqlite3.Row]:
        like = f"%{query.strip()}%"
        return self.db.fetchall(
            """
            SELECT * FROM cards
            WHERE deleted_at IS NULL
              AND (external_id LIKE ? OR title LIKE ? OR text LIKE ?)
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT ?
            """,
            (like, like, like, limit),
        )

    def save_version(
        self,
        card_id: int,
        changed_by: int | None,
        change_reason: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        executor = conn or self.db
        card = self.get(card_id, conn)
        if not card:
            return
        next_version = executor.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS version FROM card_versions WHERE card_id = ?",
            (card_id,),
        ).fetchone()["version"]
        snapshot = {key: card[key] for key in card.keys()}
        snapshot["_required_items"] = [
            row["item_code"]
            for row in executor.execute(
                "SELECT item_code FROM card_required_items WHERE card_id = ? ORDER BY item_code",
                (card_id,),
            ).fetchall()
        ]
        snapshot["_collections"] = [
            row["collection_code"]
            for row in executor.execute(
                """
                SELECT collection_code
                FROM card_collection_items
                WHERE card_id = ?
                ORDER BY collection_code
                """,
                (card_id,),
            ).fetchall()
        ]
        executor.execute(
            """
            INSERT INTO card_versions (card_id, version_number, snapshot_json, changed_by, change_reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (card_id, next_version, json.dumps(snapshot, ensure_ascii=False), changed_by, change_reason),
        )

    def list_versions(self, card_id: int, limit: int = 10) -> list[sqlite3.Row]:
        return self.db.fetchall(
            """
            SELECT id, card_id, version_number, changed_by, change_reason, created_at
            FROM card_versions
            WHERE card_id = ?
            ORDER BY version_number DESC
            LIMIT ?
            """,
            (card_id, limit),
        )

    def get_version(self, card_id: int, version_id: int) -> sqlite3.Row | None:
        return self.db.fetchone(
            """
            SELECT *
            FROM card_versions
            WHERE id = ? AND card_id = ?
            """,
            (version_id, card_id),
        )

    def set_status(
        self,
        card_id: int,
        review_status: str,
        is_enabled: bool,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        executor = conn or self.db
        executor.execute(
            """
            UPDATE cards
            SET review_status = ?, is_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (review_status, 1 if is_enabled else 0, card_id),
        )

    def duplicate(self, card_id: int, external_id: str, conn: sqlite3.Connection | None = None) -> int:
        card = self.get(card_id, conn)
        if not card:
            raise ValueError("card not found")
        data = {col: card[col] for col in CARD_COLUMNS}
        data["external_id"] = external_id
        data["review_status"] = "draft"
        data["is_enabled"] = 0
        required_items = [
            row["item_code"]
            for row in (conn or self.db).execute(
                "SELECT item_code FROM card_required_items WHERE card_id = ?",
                (card_id,),
            ).fetchall()
        ]
        collections = [
            row["collection_code"]
            for row in (conn or self.db).execute(
                "SELECT collection_code FROM card_collection_items WHERE card_id = ?",
                (card_id,),
            ).fetchall()
        ]
        return self.upsert(data, required_items, collections, conn)

    @staticmethod
    def _clean_card_data(data: dict[str, Any]) -> dict[str, Any]:
        clean = {col: data.get(col) for col in CARD_COLUMNS}
        clean["level"] = int(clean.get("level") or 1)
        clean["category"] = clean.get("category") or "task"
        clean["intensity"] = clean.get("intensity") or "light"
        clean["text"] = str(clean.get("text") or "").strip()
        clean["avoid_if_tags"] = dump_json_list(parse_json_list(clean.get("avoid_if_tags")))
        clean["risk_tags"] = dump_json_list(parse_json_list(clean.get("risk_tags")))
        clean["timer_seconds"] = int(clean["timer_seconds"]) if clean.get("timer_seconds") else None
        clean["aftercare_required"] = int(clean.get("aftercare_required") or 0)
        clean["item_mode"] = clean.get("item_mode") or "none"
        clean["is_enabled"] = int(clean.get("is_enabled") or 0)
        clean["review_status"] = clean.get("review_status") or "draft"
        return clean

    def count_cards(
        self,
        *,
        level: int | None = None,
        category: str | None = None,
        collection_code: str | None = None,
        include_archived: bool = False,
    ) -> int:
        where = ["c.deleted_at IS NULL"]
        params: list[object] = []
        if not include_archived:
            where.append("c.is_archived = 0")
        if level is not None:
            where.append("c.level = ?")
            params.append(level)
        if category:
            where.append("c.category = ?")
            params.append(category)
        if collection_code:
            where.append(
                "EXISTS (SELECT 1 FROM card_collection_items cci "
                "WHERE cci.card_id = c.id AND cci.collection_code = ?)"
            )
            params.append(collection_code)
        row = self.db.fetchone(
            f"SELECT COUNT(*) AS count FROM cards c WHERE {' AND '.join(where)}",
            params,
        )
        return int(row["count"])

    def set_archived(
        self,
        card_id: int,
        archived: bool,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        executor = conn or self.db
        executor.execute(
            """
            UPDATE cards
            SET is_archived = ?,
                is_enabled = CASE WHEN ? = 1 THEN 0 ELSE is_enabled END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
            """,
            (1 if archived else 0, 1 if archived else 0, card_id),
        )

    def soft_delete(self, card_id: int, conn: sqlite3.Connection | None = None) -> None:
        executor = conn or self.db
        executor.execute(
            """
            UPDATE cards
            SET deleted_at = CURRENT_TIMESTAMP,
                is_archived = 1,
                is_enabled = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (card_id,),
        )
