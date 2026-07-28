from __future__ import annotations

import json
from typing import Any

from app.services.content_importer import ContentImporter, ImportReport
from app.storage import Database
from app.storage.repositories.admin_actions import AdminActionRepository
from app.storage.repositories.cards import CARD_COLUMNS, CardRepository
from app.storage.repositories.items import ItemRepository


class AdminService:
    def __init__(self, db: Database):
        self.db = db
        self.cards = CardRepository(db)
        self.items = ItemRepository(db)
        self.actions = AdminActionRepository(db)
        self.importer = ContentImporter(db)

    def create_or_update_card(
        self,
        admin_user_id: int,
        card_data: dict[str, Any],
        required_items: list[str] | None = None,
        collections: list[str] | None = None,
    ) -> int:
        required_items = required_items or []
        if required_items:
            card_data = {**card_data, "item_mode": "required"}
        with self.db.transaction() as conn:
            existing = self.cards.get_by_external_id(str(card_data.get("external_id")), conn)
            if existing:
                self.cards.save_version(int(existing["id"]), admin_user_id, "admin_update", conn)
            card_id = self.cards.upsert(card_data, required_items, collections or [], conn)
            action = "update_card" if existing else "create_card"
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, ?, 'card', ?, '{}')
                """,
                (admin_user_id, action, str(card_id)),
            )
            return card_id

    def approve_card(self, admin_user_id: int, card_id: int) -> None:
        with self.db.transaction() as conn:
            self.cards.save_version(card_id, admin_user_id, "approve_card", conn)
            self.cards.set_status(card_id, "approved", True, conn)
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'approve_card', 'card', ?, '{}')
                """,
                (admin_user_id, str(card_id)),
            )

    def disable_card(self, admin_user_id: int, card_id: int) -> None:
        with self.db.transaction() as conn:
            self.cards.save_version(card_id, admin_user_id, "disable_card", conn)
            self.cards.set_status(card_id, "disabled", False, conn)
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'disable_card', 'card', ?, '{}')
                """,
                (admin_user_id, str(card_id)),
            )

    def update_card_text(self, admin_user_id: int, card_id: int, text: str) -> None:
        with self.db.transaction() as conn:
            self.cards.save_version(card_id, admin_user_id, "edit_text", conn)
            conn.execute(
                """
                UPDATE cards
                SET text = ?,
                    review_status = 'draft',
                    is_enabled = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (text, card_id),
            )
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'update_card', 'card', ?, '{}')
                """,
                (admin_user_id, str(card_id)),
            )

    def duplicate_card(self, admin_user_id: int, card_id: int, external_id: str) -> int:
        with self.db.transaction() as conn:
            new_id = self.cards.duplicate(card_id, external_id, conn)
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'duplicate_card', 'card', ?, '{}')
                """,
                (admin_user_id, str(new_id)),
            )
            return new_id

    def list_by_status(self, status: str, limit: int = 10, offset: int = 0):
        return self.cards.list_cards(review_status=status, limit=limit, offset=offset)

    def get_card(self, card_id: int):
        return self.cards.get(card_id)

    def get_card_detail(self, card_id: int) -> dict[str, Any] | None:
        row = self.cards.get(card_id)
        if not row:
            return None
        result = dict(row)
        result["required_items"] = self.db.fetchall(
            """
            SELECT i.code, i.name
            FROM card_required_items cri
            JOIN items i ON i.code = cri.item_code
            WHERE cri.card_id = ?
            ORDER BY i.name
            """,
            (card_id,),
        )
        result["collections"] = [
            collection["collection_code"]
            for collection in self.db.fetchall(
                "SELECT collection_code FROM card_collection_items WHERE card_id = ?",
                (card_id,),
            )
        ]
        return result

    def list_card_versions(self, card_id: int, limit: int = 10):
        return self.cards.list_versions(card_id, limit)

    def get_card_version(self, card_id: int, version_id: int) -> dict[str, Any] | None:
        row = self.cards.get_version(card_id, version_id)
        if not row:
            return None
        result = dict(row)
        result["snapshot"] = json.loads(str(row["snapshot_json"]))
        return result

    def restore_card_version(self, admin_user_id: int, card_id: int, version_id: int) -> None:
        with self.db.transaction() as conn:
            version = conn.execute(
                "SELECT * FROM card_versions WHERE id = ? AND card_id = ?",
                (version_id, card_id),
            ).fetchone()
            current = self.cards.get(card_id, conn)
            if not version or not current:
                raise ValueError("Версия карточки не найдена")
            snapshot = json.loads(str(version["snapshot_json"]))
            if not isinstance(snapshot, dict):
                raise ValueError("Снимок версии поврежден")
            self.cards.save_version(
                card_id,
                admin_user_id,
                f"before_restore_version_{version['version_number']}",
                conn,
            )
            current_items = [
                row["item_code"]
                for row in conn.execute(
                    "SELECT item_code FROM card_required_items WHERE card_id = ?",
                    (card_id,),
                ).fetchall()
            ]
            current_collections = [
                row["collection_code"]
                for row in conn.execute(
                    "SELECT collection_code FROM card_collection_items WHERE card_id = ?",
                    (card_id,),
                ).fetchall()
            ]
            card_data = {
                column: snapshot.get(column, current[column])
                for column in CARD_COLUMNS
            }
            required_items = snapshot.get("_required_items", current_items)
            collections = snapshot.get("_collections", current_collections)
            self.cards.upsert(card_data, list(required_items), list(collections), conn)
            conn.execute(
                """
                UPDATE cards
                SET is_archived = ?, deleted_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    int(snapshot.get("is_archived", current["is_archived"])),
                    snapshot.get("deleted_at", current["deleted_at"]),
                    card_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO admin_actions (
                    admin_user_id, action_type, target_type, target_id, details_json
                )
                VALUES (?, 'rollback_card', 'card', ?, ?)
                """,
                (
                    admin_user_id,
                    str(card_id),
                    json.dumps(
                        {"restored_version": int(version["version_number"])},
                        ensure_ascii=False,
                    ),
                ),
            )

    def list_seed_conflicts(self, limit: int = 10):
        return self.db.fetchall(
            """
            SELECT sc.*, c.text AS current_text, c.title AS current_title
            FROM seed_conflicts sc
            JOIN cards c ON c.id = sc.card_id
            WHERE sc.status = 'pending'
            ORDER BY sc.created_at DESC, sc.id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_seed_conflict(self, conflict_id: int) -> dict[str, Any] | None:
        row = self.db.fetchone(
            """
            SELECT sc.*, c.text AS current_text, c.title AS current_title
            FROM seed_conflicts sc
            JOIN cards c ON c.id = sc.card_id
            WHERE sc.id = ?
            """,
            (conflict_id,),
        )
        if not row:
            return None
        result = dict(row)
        result["incoming"] = json.loads(str(row["incoming_json"]))
        return result

    def resolve_seed_conflict(
        self,
        admin_user_id: int,
        conflict_id: int,
        *,
        apply_seed: bool,
    ) -> int:
        with self.db.transaction() as conn:
            conflict = conn.execute(
                "SELECT * FROM seed_conflicts WHERE id = ? AND status = 'pending'",
                (conflict_id,),
            ).fetchone()
            if not conflict:
                raise ValueError("Конфликт уже решен или не найден")
            card_id = int(conflict["card_id"])
            if apply_seed:
                incoming = json.loads(str(conflict["incoming_json"]))
                self.cards.save_version(card_id, admin_user_id, "before_seed_update", conn)
                self.cards.upsert(
                    incoming["card"],
                    list(incoming.get("required_items", [])),
                    list(incoming.get("collections", [])),
                    conn,
                )
                self.cards.set_archived(
                    card_id,
                    bool(incoming.get("is_archived", False)),
                    conn,
                )
            status = "apply_seed" if apply_seed else "keep_local"
            conn.execute(
                """
                UPDATE seed_conflicts
                SET status = ?, resolved_by = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, admin_user_id, conflict_id),
            )
            conn.execute(
                """
                INSERT INTO admin_actions (
                    admin_user_id, action_type, target_type, target_id, details_json
                )
                VALUES (?, 'update_card', 'seed_conflict', ?, ?)
                """,
                (
                    admin_user_id,
                    str(conflict_id),
                    json.dumps({"resolution": status, "card_id": card_id}, ensure_ascii=False),
                ),
            )
            return card_id

    def list_card_feedback(self, limit: int = 10):
        return self.db.fetchall(
            """
            SELECT
                cf.id,
                cf.card_id,
                cf.player_slot,
                cf.created_at,
                c.external_id,
                c.title
            FROM card_feedback cf
            JOIN cards c ON c.id = cf.card_id
            WHERE cf.status = 'new'
            ORDER BY cf.created_at DESC, cf.id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_card_feedback(self, feedback_id: int):
        return self.db.fetchone(
            """
            SELECT
                cf.*,
                c.external_id,
                c.title,
                c.text
            FROM card_feedback cf
            JOIN cards c ON c.id = cf.card_id
            WHERE cf.id = ?
            """,
            (feedback_id,),
        )

    def resolve_card_feedback(self, admin_user_id: int, feedback_id: int) -> int:
        with self.db.transaction() as conn:
            feedback = conn.execute(
                "SELECT card_id FROM card_feedback WHERE id = ? AND status = 'new'",
                (feedback_id,),
            ).fetchone()
            if not feedback:
                raise ValueError("Сообщение уже обработано или не найдено")
            conn.execute(
                """
                UPDATE card_feedback
                SET status = 'resolved',
                    resolved_by = ?,
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (admin_user_id, feedback_id),
            )
            conn.execute(
                """
                INSERT INTO admin_actions (
                    admin_user_id, action_type, target_type, target_id, details_json
                )
                VALUES (?, 'update_card', 'card_feedback', ?, '{}')
                """,
                (admin_user_id, str(feedback_id)),
            )
            return int(feedback["card_id"])

    def update_card_field(
        self,
        admin_user_id: int,
        card_id: int,
        field: str,
        value: object,
    ) -> None:
        allowed_fields = {
            "title",
            "text",
            "level",
            "category",
            "intensity",
            "timer_seconds",
            "item_mode",
        }
        if field not in allowed_fields:
            raise ValueError("Поле нельзя изменить")
        if field == "timer_seconds":
            value = int(value) if value not in (None, "", "0", 0) else None
        with self.db.transaction() as conn:
            if field == "item_mode" and value == "none":
                has_items = conn.execute(
                    "SELECT 1 FROM card_required_items WHERE card_id = ? LIMIT 1",
                    (card_id,),
                ).fetchone()
                if has_items:
                    raise ValueError("Сначала уберите обязательный реквизит из карточки")
            self.cards.save_version(card_id, admin_user_id, f"edit_{field}", conn)
            conn.execute(
                f"""
                UPDATE cards
                SET {field} = ?,
                    review_status = 'draft',
                    is_enabled = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NULL
                """,
                (value, card_id),
            )
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'update_card', 'card', ?, '{}')
                """,
                (admin_user_id, str(card_id)),
            )

    def update_card_items(
        self,
        admin_user_id: int,
        card_id: int,
        values: list[str],
    ) -> None:
        rows = self.db.fetchall(
            """
            SELECT code, name
            FROM items
            WHERE deleted_at IS NULL
            """
        )
        lookup = {}
        for row in rows:
            lookup[str(row["code"]).casefold()] = str(row["code"])
            lookup[str(row["name"]).casefold()] = str(row["code"])
        codes = []
        for value in values:
            code = lookup.get(value.strip().casefold())
            if not code:
                raise ValueError(f"Реквизит «{value.strip()}» не найден")
            if code not in codes:
                codes.append(code)
        with self.db.transaction() as conn:
            self.cards.save_version(card_id, admin_user_id, "edit_required_items", conn)
            self.cards.replace_required_items(card_id, codes, conn)
            conn.execute(
                """
                UPDATE cards
                SET item_mode = ?,
                    review_status = 'draft',
                    is_enabled = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                ("required" if codes else "none", card_id),
            )

    def list_catalog(
        self,
        *,
        level: int | None,
        category: str | None,
        extreme: bool,
        limit: int = 10,
        offset: int = 0,
    ):
        return self.cards.list_cards(
            level=None if extreme else level,
            category=category,
            collection_code="restricted_content" if extreme else None,
            include_archived=True,
            limit=limit,
            offset=offset,
        )

    def count_catalog(
        self,
        *,
        level: int | None,
        category: str | None,
        extreme: bool,
    ) -> int:
        return self.cards.count_cards(
            level=None if extreme else level,
            category=category,
            collection_code="restricted_content" if extreme else None,
            include_archived=True,
        )

    def archive_card(self, admin_user_id: int, card_id: int, archived: bool) -> None:
        with self.db.transaction() as conn:
            self.cards.save_version(card_id, admin_user_id, "archive_card" if archived else "restore_card", conn)
            self.cards.set_archived(card_id, archived, conn)
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, ?, 'card', ?, '{}')
                """,
                (admin_user_id, "archive_card" if archived else "restore_card", str(card_id)),
            )

    def delete_card(self, admin_user_id: int, card_id: int) -> None:
        with self.db.transaction() as conn:
            self.cards.save_version(card_id, admin_user_id, "delete_card", conn)
            self.cards.soft_delete(card_id, conn)
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'delete_card', 'card', ?, '{}')
                """,
                (admin_user_id, str(card_id)),
            )

    def search(self, query: str):
        return self.cards.search(query)

    def export_rows(self):
        return self.db.fetchall(
            """
            SELECT
                c.id,
                c.external_id,
                c.level,
                c.category,
                c.intensity,
                c.title,
                c.text,
                (
                    SELECT group_concat(cri.item_code, ',')
                    FROM card_required_items cri
                    WHERE cri.card_id = c.id
                ) AS required_items,
                c.timer_seconds,
                c.risk_tags,
                c.avoid_if_tags,
                (
                    SELECT group_concat(cci.collection_code, ',')
                    FROM card_collection_items cci
                    WHERE cci.card_id = c.id
                ) AS collections,
                c.review_status,
                c.is_enabled,
                c.aftercare_required,
                c.item_mode,
                c.is_archived,
                c.pose_family,
                c.pose_difficulty,
                c.space_required,
                c.body_load,
                c.notes,
                c.created_at,
                c.updated_at
            FROM cards c
            WHERE c.deleted_at IS NULL
            ORDER BY c.id
            """
        )

    def export_items(self):
        return self.db.fetchall(
            """
            SELECT
                code, name, min_level, max_level, categories, usage_text,
                randomizable, is_active, is_archived
            FROM items
            WHERE deleted_at IS NULL
            ORDER BY name
            """
        )

    def list_items(self, *, limit: int = 10, offset: int = 0):
        return self.items.list_items(include_archived=True, limit=limit, offset=offset)

    def count_items(self) -> int:
        return self.items.count(include_archived=True)

    def get_item(self, code: str):
        return self.items.get(code)

    def create_item(self, admin_user_id: int, **data: Any) -> str:
        with self.db.transaction() as conn:
            code = self.items.create(conn=conn, **data)
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'create_item', 'item', ?, '{}')
                """,
                (admin_user_id, code),
            )
            return code

    def update_item(self, admin_user_id: int, code: str, **data: Any) -> None:
        with self.db.transaction() as conn:
            self.items.update(code, conn=conn, **data)
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'update_item', 'item', ?, '{}')
                """,
                (admin_user_id, code),
            )

    def archive_item(self, admin_user_id: int, code: str, archived: bool) -> None:
        with self.db.transaction() as conn:
            self.items.set_archived(code, archived, conn)
            if archived:
                conn.execute("DELETE FROM session_items WHERE item_code = ?", (code,))
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, ?, 'item', ?, '{}')
                """,
                (admin_user_id, "archive_item" if archived else "restore_item", code),
            )

    def delete_item(self, admin_user_id: int, code: str) -> None:
        with self.db.transaction() as conn:
            self.items.soft_delete(code, conn)
            conn.execute("DELETE FROM session_items WHERE item_code = ?", (code,))
            conn.execute(
                """
                INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
                VALUES (?, 'delete_item', 'item', ?, '{}')
                """,
                (admin_user_id, code),
            )

    def list_collections(self):
        return self.db.fetchall(
            """
            SELECT cc.code, cc.name, cc.is_enabled, COUNT(cci.card_id) AS cards_count
            FROM content_collections cc
            LEFT JOIN card_collection_items cci ON cci.collection_code = cc.code
            GROUP BY cc.code, cc.name, cc.is_enabled
            ORDER BY cc.code
            """
        )

    def import_content(self, admin_user_id: int, path: str, *, dry_run: bool = True) -> ImportReport:
        return self.importer.import_file(path, dry_run=dry_run, admin_user_id=None if dry_run else admin_user_id)
