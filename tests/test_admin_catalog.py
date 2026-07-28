from __future__ import annotations

import pytest

from app.services.admin_service import AdminService
from tests.helpers import import_seed, migrated_db


def test_card_catalog_archives_and_soft_deletes_without_breaking_history(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute(
        "INSERT INTO users (telegram_id, display_name, role) VALUES (111, 'Админ', 'player_1')"
    )
    service = AdminService(db)
    card = db.fetchone("SELECT id FROM cards WHERE external_id = 'task_l1_001'")
    card_id = int(card["id"])

    service.archive_card(111, card_id, True)
    archived = service.get_card(card_id)
    assert archived["is_archived"] == 1
    assert archived["is_enabled"] == 0

    service.archive_card(111, card_id, False)
    assert service.get_card(card_id)["is_archived"] == 0

    service.delete_card(111, card_id)
    assert service.get_card(card_id)["deleted_at"] is not None
    assert all(row["id"] != card_id for row in service.list_catalog(
        level=1,
        category="task",
        extreme=False,
    ))
    assert db.fetchone(
        "SELECT COUNT(*) AS count FROM card_versions WHERE card_id = ?",
        (card_id,),
    )["count"] == 3
    db.close()


def test_item_catalog_supports_create_edit_archive_and_delete(tmp_path):
    db = migrated_db(tmp_path)
    db.execute(
        "INSERT INTO users (telegram_id, display_name, role) VALUES (111, 'Админ', 'player_1')"
    )
    service = AdminService(db)
    code = service.create_item(
        111,
        name="Тестовый реквизит",
        min_level=2,
        max_level=4,
        categories=["task", "desire"],
        usage_text="Используйте только согласованным способом и сразу уберите по просьбе.",
        randomizable=True,
    )

    service.update_item(111, code, name="Обновленный реквизит")
    assert service.get_item(code)["name"] == "Обновленный реквизит"
    service.archive_item(111, code, True)
    assert service.get_item(code)["is_archived"] == 1
    assert service.get_item(code)["is_active"] == 0
    service.archive_item(111, code, False)
    assert service.get_item(code)["is_active"] == 1
    service.delete_item(111, code)
    assert service.get_item(code)["deleted_at"] is not None
    db.close()


def test_card_item_edit_keeps_mode_and_explicit_items_consistent(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute(
        "INSERT INTO users (telegram_id, display_name, role) VALUES (111, 'Админ', 'player_1')"
    )
    service = AdminService(db)
    card = db.fetchone("SELECT id FROM cards WHERE external_id = 'task_l1_001'")
    card_id = int(card["id"])

    service.update_card_items(111, card_id, ["Повязка"])
    detail = service.get_card_detail(card_id)
    assert detail["item_mode"] == "required"
    assert [row["code"] for row in detail["required_items"]] == ["blindfold"]

    with pytest.raises(ValueError, match="Сначала уберите"):
        service.update_card_field(111, card_id, "item_mode", "none")

    service.update_card_items(111, card_id, [])
    detail = service.get_card_detail(card_id)
    assert detail["item_mode"] == "none"
    assert detail["required_items"] == []
    db.close()
