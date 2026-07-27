from __future__ import annotations

from typing import Any

from app.services.content_importer import ContentImporter, ImportReport
from app.storage import Database
from app.storage.repositories.admin_actions import AdminActionRepository
from app.storage.repositories.cards import CardRepository


class AdminService:
    def __init__(self, db: Database):
        self.db = db
        self.cards = CardRepository(db)
        self.actions = AdminActionRepository(db)
        self.importer = ContentImporter(db)

    def create_or_update_card(
        self,
        admin_user_id: int,
        card_data: dict[str, Any],
        required_items: list[str] | None = None,
        collections: list[str] | None = None,
    ) -> int:
        with self.db.transaction() as conn:
            existing = self.cards.get_by_external_id(str(card_data.get("external_id")), conn)
            if existing:
                self.cards.save_version(int(existing["id"]), admin_user_id, "admin_update", conn)
            card_id = self.cards.upsert(card_data, required_items or [], collections or [], conn)
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

    def search(self, query: str):
        return self.cards.search(query)

    def export_rows(self):
        return self.db.fetchall(
            """
            SELECT id, external_id, level, category, intensity, review_status, is_enabled, text
            FROM cards
            ORDER BY id
            """
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
