from __future__ import annotations

import csv
import shutil
from pathlib import Path

from app.services.content_importer import ContentImporter
from app.storage import Database


REWRITTEN_IDS = {
    "task_l1_013",
    "task_l1_017",
    "task_l1_019",
    "task_l4_light_015",
    "question_seed_003",
    "question_seed_004",
    "desire_seed_001",
    "desire_seed_004",
}

REMOVED_DUPLICATES = {
    "task_l1_010": (1, "task"),
    "task_l1_011": (1, "task"),
    "task_l1_018": (1, "task"),
    "task_l1_020": (1, "task"),
    "task_l1_021": (1, "task"),
    "task_l1_023": (1, "task"),
    "task_l2_004": (2, "task"),
    "task_l4_hard_004": (4, "task"),
    "task_l4_hard_014": (4, "task"),
    "task_l4_medium_008": (4, "task"),
    "task_l4_medium_016": (4, "task"),
    "pose_ks_031": (3, "pose"),
    "pose_ks_035": (4, "pose"),
    "penalty_seed_002": (1, "penalty"),
    "restricted_l4_hard_urethral_002": (4, "question"),
    "restricted_q_002": (4, "question"),
}


def test_full_semantic_audit_migration_updates_and_archives_duplicates(tmp_path):
    migration_source = Path("app/storage/migrations")
    old_migrations = tmp_path / "old_migrations"
    old_migrations.mkdir()
    for source in sorted(migration_source.glob("*.sql")):
        if source.name < "018_full_card_semantic_audit.sql":
            shutil.copy2(source, old_migrations / source.name)

    db = Database(tmp_path / "bot.sqlite3")
    db.apply_migrations(old_migrations)
    ContentImporter(db).import_file(Path("content/cards.csv"), dry_run=False)

    db.execute(
        """
        UPDATE cards
        SET title = 'Старое название',
            text = 'Старый текст',
            review_status = 'needs_review'
        WHERE external_id IN (
            'task_l1_017',
            'task_l1_019',
            'task_l1_013',
            'task_l4_light_015',
            'question_seed_003',
            'question_seed_004',
            'desire_seed_001',
            'desire_seed_004'
        )
        """
    )
    db.execute(
        """
        UPDATE cards
        SET text = 'Контекст: Одинаковый сценарий.

Порядок: Одинаковый сценарий.

Дополнительное правило этой карточки: Выполняйте последовательность. Новое правило.

Завершение: Конец.'
        WHERE external_id = 'task_l3_light_001'
        """
    )
    db.execute(
        """
        UPDATE cards
        SET text = 'Исходное положение: На кровати.

Назначение: Конкретное действие.

Действие: Конкретное действие. Продолжайте только это действие до сигнала таймера.

Завершение: Конец.'
        WHERE external_id = 'pose_ks_001'
        """
    )
    db.executemany(
        """
        INSERT INTO cards (
            external_id, level, category, intensity, title, text,
            review_status, is_enabled
        )
        VALUES (?, ?, ?, 'light', 'Дубль', 'Повторяющийся текст', 'needs_review', 1)
        """,
        [
            (external_id, level, category)
            for external_id, (level, category) in REMOVED_DUPLICATES.items()
        ],
    )

    db.apply_migrations()

    with Path("content/cards.csv").open(encoding="utf-8-sig", newline="") as source:
        expected_rows = {
            row["external_id"]: row
            for row in csv.DictReader(source)
            if row["external_id"] in REWRITTEN_IDS
        }

    for external_id in sorted(REWRITTEN_IDS):
        rewritten = db.fetchone(
            """
            SELECT title, text, timer_seconds, review_status, is_enabled
            FROM cards
            WHERE external_id = ?
            """,
            (external_id,),
        )
        expected = expected_rows[external_id]
        assert rewritten["title"] == expected["title"]
        assert rewritten["text"] == expected["text"]
        assert rewritten["timer_seconds"] == (
            int(expected["timer_seconds"]) if expected["timer_seconds"] else None
        )
        assert rewritten["review_status"] == "approved"
        assert rewritten["is_enabled"] == 1

    for external_id in REMOVED_DUPLICATES:
        duplicate = db.fetchone(
            """
            SELECT review_status, is_enabled, is_archived, deleted_at
            FROM cards
            WHERE external_id = ?
            """,
            (external_id,),
        )
        assert duplicate["review_status"] == "disabled"
        assert duplicate["is_enabled"] == 0
        assert duplicate["is_archived"] == 1
        assert duplicate["deleted_at"]

    normalized_task = db.fetchone(
        "SELECT text FROM cards WHERE external_id = 'task_l3_light_001'"
    )["text"]
    assert normalized_task.startswith("Порядок: Одинаковый сценарий.")
    assert "Контекст: Одинаковый сценарий." not in normalized_task
    assert "Выполняйте последовательность" not in normalized_task

    normalized_pose = db.fetchone(
        "SELECT text FROM cards WHERE external_id = 'pose_ks_001'"
    )["text"]
    assert "Назначение:" not in normalized_pose
    assert "Действие: Конкретное действие." in normalized_pose
    assert "Продолжайте только это действие до сигнала таймера" not in normalized_pose
    db.close()
