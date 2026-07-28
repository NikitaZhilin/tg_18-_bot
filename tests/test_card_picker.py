from __future__ import annotations

import pytest

from app.services.card_picker import NoCardsAvailable
from app.services.game_service import GameError, GameService, format_card
from tests.helpers import import_restricted_seed, import_seed, make_config, make_single_account_config, migrated_db


def test_draws_only_approved_cards_and_prevents_repeats(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    first = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    service.finish_turn(10, None, 111)
    second = service.draw_card(10, None, 222, level=1, category="task", intensity="light")
    assert first.card.id != second.card.id
    assert first.card.level == 1
    assert second.card.category == "task"
    db.close()


def test_hard_cards_are_available_without_duplicate_mode_toggle(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    result = service.draw_card(10, None, 111, level=3, category="task", intensity="hard")
    assert result.card.intensity == "hard"
    db.close()


def test_base_consent_required_before_draw(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    with pytest.raises(GameError):
        service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    with pytest.raises(GameError, match="Сейчас подтверждает A"):
        service.accept_base_consent(10, None, 222)
    assert service.accept_base_consent(10, None, 111) is False
    assert service.accept_base_consent(10, None, 222) is True
    db.close()


def test_session_boundaries_filter_cards(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    service.set_boundaries_for_active_session(10, None, ["seed_only"], 111)
    db.execute("UPDATE cards SET avoid_if_tags = '[\"seed_only\"]' WHERE level = 1 AND category = 'task'")
    with pytest.raises(NoCardsAvailable):
        service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    db.close()


def test_bdsm_level_is_available_without_duplicate_level_toggle(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    result = service.draw_card(10, None, 111, level=4, category="task", intensity="light")
    assert result.card.level == 4
    db.close()


def test_desire_card_is_saved_as_coupon(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    result = service.draw_card(10, None, 111, level=2, category="desire", intensity="light")
    saved = db.fetchone("SELECT * FROM saved_desires WHERE card_id = ?", (result.card.id,))
    assert saved is not None
    assert saved["owner_id"] == 111
    assert saved["owner_slot"] == "player_1"
    assert saved["granted_by_slot"] == "player_2"
    db.close()


def test_single_account_mode_uses_virtual_player_slots(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_single_account_config(tmp_path))
    service.ensure_session(10, None)
    assert service.accept_base_consent(10, None, 111) is False
    assert service.accept_base_consent(10, None, 111) is True

    first = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    turn = db.fetchone("SELECT * FROM turns WHERE id = ?", (first.turn_id,))
    assert turn["player_slot"] == "player_1"

    next_player = service.finish_turn(10, None, 111)
    assert next_player == "Игрок 2"
    status = service.status(10, None)
    assert status["current_player_id"] == 111
    assert status["current_player_slot"] == "player_2"

    second = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    second_turn = db.fetchone("SELECT * FROM turns WHERE id = ?", (second.turn_id,))
    assert second_turn["player_slot"] == "player_2"
    db.close()


def test_level_roulette_limits_cards_to_selected_level(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    result = service.draw_card(10, None, 111, level=2, category=None, intensity=None, source="roulette")
    assert result.card.level == 2
    db.close()


def test_roulette_does_not_repeat_used_cards_in_session(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    first = service.draw_card(10, None, 111, level=1, category=None, intensity=None, source="roulette")
    service.finish_turn(10, None, 111)
    second = service.draw_card(10, None, 222, level=1, category=None, intensity=None, source="roulette")

    assert first.card.id != second.card.id
    used = db.fetchone("SELECT COUNT(*) AS count FROM used_cards WHERE session_id = 1")
    assert used["count"] == 2
    db.close()


def test_finishing_turn_is_idempotent_and_restricted_to_current_player(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    service.draw_card(10, None, 111, level=1, category="task", intensity="light")

    with pytest.raises(GameError, match="другого игрока"):
        service.finish_turn(10, None, 222)

    assert service.finish_turn(10, None, 111) == "B"
    with pytest.raises(GameError, match="Активной карточки нет"):
        service.finish_turn(10, None, 111)
    assert service.status(10, None)["current_player_id"] == 222
    db.close()


def test_restricted_cards_require_session_unlock(tmp_path):
    db = migrated_db(tmp_path)
    import_restricted_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    with pytest.raises(GameError, match="Экстрим"):
        service.draw_card(
            10,
            None,
            111,
            level=None,
            category=None,
            collection_code="restricted_content",
        )

    service.unlock_restricted_content(10, None)
    result = service.draw_card(
        10,
        None,
        111,
        level=None,
        category=None,
        collection_code="restricted_content",
    )
    assert result.card.external_id.startswith("restricted_")
    assert result.card.level == 4
    assert result.card.intensity == "hard"
    assert format_card(result.card).startswith("Экстрим ·")
    db.close()


def test_card_header_uses_level_category_and_section_number(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute("UPDATE cards SET is_enabled = 0")
    db.execute("UPDATE cards SET is_enabled = 1 WHERE external_id = 'task_l2_021'")
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    result = service.draw_card(10, None, 111, level=2, category="task", intensity="light")
    text = format_card(result.card)

    assert text.startswith("Разогрев · Задание №20")
    assert "Что нужно сделать:" in text
    assert "Уровень 2 - 21" not in text
    assert "дышит в собственном обычном ритме" in text
    db.close()


def test_active_card_can_be_resumed_and_blocks_new_draw(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    first = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    resumed = service.current_card(10, None)

    assert resumed is not None
    assert resumed.turn_id == first.turn_id
    assert resumed.card.id == first.card.id
    with pytest.raises(GameError, match="текущую карточку"):
        service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    db.close()


def test_inventory_frequency_and_required_item_are_saved_with_turn(tmp_path):
    db = migrated_db(tmp_path)
    import_restricted_seed(db)
    db.execute("UPDATE cards SET is_enabled = 0")
    db.execute("UPDATE cards SET is_enabled = 1 WHERE external_id = 'restricted_l4_hard_fisting_001'")
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    service.unlock_restricted_content(10, None)
    service.set_items_for_active_session(10, None, {"gloves": 3, "lubricant": 1})

    result = service.draw_card(
        10,
        None,
        111,
        level=None,
        category="task",
        collection_code="restricted_content",
    )
    turn = db.fetchone("SELECT selected_item_code FROM turns WHERE id = ?", (result.turn_id,))
    resumed = service.current_card(10, None)

    assert service.items_for_active_session(10, None) == {"gloves": 3, "lubricant": 1}
    assert {item[0] for item in result.card.required_items} == {
        "Лубрикант",
        "Одноразовые перчатки",
    }
    assert result.card.selected_item_code is None
    assert turn["selected_item_code"] is None
    assert resumed is not None
    assert resumed.card.selected_item_code == result.card.selected_item_code
    assert "Обязательный реквизит:" in format_card(result.card)
    db.close()


def test_replace_card_keeps_player_and_filters_but_draws_another_card(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    first = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    replacement = service.replace_active_card(10, None, 111)

    assert replacement.card.id != first.card.id
    assert replacement.card.level == first.card.level == 1
    assert replacement.card.category == first.card.category == "task"
    status = service.status(10, None)
    assert status["current_player_id"] == 111
    turns = db.fetchall("SELECT status, player_id FROM turns ORDER BY id")
    assert [(row["status"], row["player_id"]) for row in turns] == [
        ("skipped", 111),
        ("active", 111),
    ]
    db.close()


def test_replace_keeps_current_card_when_no_replacement_exists(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute("UPDATE cards SET is_enabled = 0")
    db.execute("UPDATE cards SET is_enabled = 1 WHERE external_id = 'task_l1_001'")
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    first = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    with pytest.raises(NoCardsAvailable):
        service.replace_active_card(10, None, 111)

    current = service.current_card(10, None)
    assert current is not None
    assert current.turn_id == first.turn_id
    assert current.card.id == first.card.id
    turn = db.fetchone("SELECT status FROM turns WHERE id = ?", (first.turn_id,))
    assert turn["status"] == "active"
    db.close()


def test_revision_request_disables_card_and_atomically_draws_replacement(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    first = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    replacement = service.request_card_revision(10, None, 111, first.turn_id)

    assert replacement is not None
    assert replacement.card.id != first.card.id
    marked = db.fetchone(
        "SELECT review_status, is_enabled FROM cards WHERE id = ?",
        (first.card.id,),
    )
    assert marked["review_status"] == "needs_review"
    assert int(marked["is_enabled"]) == 0
    feedback = db.fetchone(
        "SELECT status FROM card_feedback WHERE turn_id = ?",
        (first.turn_id,),
    )
    assert feedback["status"] == "new"
    assert service.current_card(10, None).turn_id == replacement.turn_id
    db.close()


def test_revision_request_marks_card_even_when_replacement_is_unavailable(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute("UPDATE cards SET is_enabled = 0")
    db.execute("UPDATE cards SET is_enabled = 1 WHERE external_id = 'task_l1_001'")
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    first = service.draw_card(10, None, 111, level=1, category="task", intensity="light")
    replacement = service.request_card_revision(10, None, 111, first.turn_id)

    assert replacement is None
    assert service.current_card(10, None) is None
    status = service.status(10, None)
    assert status["current_player_id"] == 111
    marked = db.fetchone(
        "SELECT review_status, is_enabled FROM cards WHERE id = ?",
        (first.card.id,),
    )
    assert marked["review_status"] == "needs_review"
    assert int(marked["is_enabled"]) == 0
    turn = db.fetchone("SELECT status FROM turns WHERE id = ?", (first.turn_id,))
    assert turn["status"] == "skipped"
    db.close()


def test_roulette_uses_session_default_levels(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    service.set_enabled_level(10, None, 1, False)
    service.set_enabled_level(10, None, 2, False)

    result = service.draw_card(
        10,
        None,
        111,
        level=None,
        category=None,
        source="roulette",
    )

    assert service.enabled_levels(10, None) == (3, 4)
    assert result.card.level in {3, 4}
    db.close()
