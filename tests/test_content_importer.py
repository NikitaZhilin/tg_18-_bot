from __future__ import annotations

import csv
from pathlib import Path

from app.services.admin_service import AdminService
from app.services.content_importer import ContentImporter
from app.storage.repositories.cards import CardRepository
from tests.helpers import import_restricted_seed, import_seed, migrated_db


def test_seed_content_counts_match_tz(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    rows = db.fetchall(
        """
        SELECT level, COUNT(*) AS count
        FROM cards
        WHERE category = 'task'
        GROUP BY level
        ORDER BY level
        """
    )
    assert [(row["level"], row["count"]) for row in rows] == [(1, 24), (2, 24), (3, 48), (4, 48)]
    pose_count = db.fetchone("SELECT COUNT(*) AS count FROM cards WHERE category = 'pose'")["count"]
    assert pose_count == 36
    db.close()


def test_hard_and_level4_built_in_seed_cards_are_reviewed(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    row = db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM cards
        WHERE (level = 4 OR intensity = 'hard')
          AND review_status = 'approved'
          AND is_enabled = 1
        """
    )
    assert row["count"] == 79
    db.close()


def test_restricted_content_imports_into_closed_collection(tmp_path):
    db = migrated_db(tmp_path)
    import_restricted_seed(db)
    row = db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM cards c
        JOIN card_collection_items cci ON cci.card_id = c.id
        WHERE cci.collection_code = 'restricted_content'
          AND c.review_status = 'approved'
          AND c.is_enabled = 1
        """
    )
    assert row["count"] == 19
    drafts = db.fetchall(
        """
        SELECT external_id, review_status, is_enabled
        FROM cards
        WHERE external_id LIKE 'restricted_l4_hard_%_progression_draft'
           OR external_id = 'restricted_l4_hard_rope_restraint_draft'
        ORDER BY external_id
        """
    )
    assert len(drafts) == 3
    assert all(row["review_status"] == "draft" and row["is_enabled"] == 0 for row in drafts)
    db.close()


def test_startup_seed_does_not_overwrite_admin_changes(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    card = db.fetchone("SELECT id FROM cards WHERE external_id = 'task_l1_001'")
    CardRepository(db).save_version(int(card["id"]), None, "admin_edit")
    db.execute(
        """
        UPDATE cards
        SET text = 'Текст, измененный администратором'
        WHERE external_id = 'task_l1_001'
        """
    )
    second_card = db.fetchone("SELECT id FROM cards WHERE external_id = 'task_l1_002'")
    CardRepository(db).save_version(int(second_card["id"]), None, "admin_edit")
    db.execute(
        """
        UPDATE cards
        SET text = 'Вторая локальная версия'
        WHERE external_id = 'task_l1_002'
        """
    )

    report = ContentImporter(db).import_file(
        Path("content/cards.csv"),
        dry_run=False,
        preserve_admin_changes=True,
    )

    card = db.fetchone("SELECT text FROM cards WHERE external_id = 'task_l1_001'")
    assert card["text"] == "Текст, измененный администратором"
    assert report.added_or_updated == 194
    assert report.conflicts == 2
    conflict = db.fetchone(
        "SELECT id, status FROM seed_conflicts WHERE external_id = 'task_l1_001'"
    )
    assert conflict["status"] == "pending"

    db.execute(
        "INSERT INTO users (telegram_id, display_name, role) VALUES (111, 'Админ', 'player_1')"
    )
    AdminService(db).resolve_seed_conflict(111, int(conflict["id"]), apply_seed=True)
    restored = db.fetchone("SELECT text FROM cards WHERE external_id = 'task_l1_001'")
    assert restored["text"] != "Текст, измененный администратором"
    assert db.fetchone(
        "SELECT status FROM seed_conflicts WHERE id = ?",
        (conflict["id"],),
    )["status"] == "apply_seed"
    keep_conflict = db.fetchone(
        "SELECT id FROM seed_conflicts WHERE external_id = 'task_l1_002'"
    )
    AdminService(db).resolve_seed_conflict(
        111,
        int(keep_conflict["id"]),
        apply_seed=False,
    )
    assert db.fetchone(
        "SELECT text FROM cards WHERE external_id = 'task_l1_002'"
    )["text"] == "Вторая локальная версия"
    assert db.fetchone(
        "SELECT status FROM seed_conflicts WHERE id = ?",
        (keep_conflict["id"],),
    )["status"] == "keep_local"
    db.close()


def test_startup_seed_updates_unmodified_built_in_cards(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute(
        """
        UPDATE cards
        SET text = 'Старый текст из предыдущей версии'
        WHERE external_id = 'task_l1_001'
        """
    )

    ContentImporter(db).import_file(
        Path("content/cards.csv"),
        dry_run=False,
        preserve_admin_changes=True,
    )

    card = db.fetchone("SELECT text FROM cards WHERE external_id = 'task_l1_001'")
    assert card["text"] != "Старый текст из предыдущей версии"
    db.close()


def test_startup_seed_version_is_applied_only_once(tmp_path):
    db = migrated_db(tmp_path)
    importer = ContentImporter(db)
    version = "startup_seed:test:abc"

    first = importer.import_file(
        Path("content/cards.csv"),
        content_version=version,
        dry_run=False,
        skip_imported_version=True,
    )
    second = importer.import_file(
        Path("content/cards.csv"),
        content_version=version,
        dry_run=False,
        skip_imported_version=True,
    )

    assert first.added_or_updated == 196
    assert second.added_or_updated == 0
    db.close()


def test_import_rejects_unknown_item_reference(tmp_path):
    db = migrated_db(tmp_path)
    path = tmp_path / "unknown_item.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "external_id",
                "level",
                "category",
                "text",
                "required_items",
                "item_mode",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "external_id": "test_unknown_item",
                "level": 1,
                "category": "task",
                "text": "Понятный тестовый текст карточки.",
                "required_items": "missing_item",
                "item_mode": "required",
            }
        )

    report = ContentImporter(db).import_file(path, dry_run=True)

    assert report.added_or_updated == 0
    assert report.warnings_count == 1
    assert "Неизвестный реквизит" in report.warnings[0].message
    db.close()


def test_import_rejects_explicit_item_with_disabled_item_mode(tmp_path):
    db = migrated_db(tmp_path)
    path = tmp_path / "inconsistent_item_mode.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "external_id",
                "level",
                "category",
                "text",
                "required_items",
                "item_mode",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "external_id": "test_inconsistent_item_mode",
                "level": 2,
                "category": "task",
                "text": "Используйте выбранную повязку только согласованным способом.",
                "required_items": "blindfold",
                "item_mode": "none",
            }
        )

    report = ContentImporter(db).import_file(path, dry_run=True)

    assert report.added_or_updated == 0
    assert report.warnings_count == 1
    assert "Обязательно подобрать" in report.warnings[0].message
    db.close()
