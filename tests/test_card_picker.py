from __future__ import annotations

import pytest

from app.services.card_picker import NoCardsAvailable
from app.services.game_service import GameError, GameService
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


def test_hard_requires_consent_and_reviewed_cards(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    with pytest.raises(GameError):
        service.draw_card(10, None, 111, level=3, category="task", intensity="hard")
    service.set_hard_consent(10, None, 111, True)
    service.set_hard_consent(10, None, 222, True)
    with pytest.raises(NoCardsAvailable):
        service.draw_card(10, None, 111, level=3, category="task", intensity="hard")
    db.close()


def test_base_consent_required_before_draw(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    with pytest.raises(GameError):
        service.draw_card(10, None, 111, level=1, category="task", intensity="light")
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


def test_level4_requires_two_consents(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    with pytest.raises(GameError):
        service.draw_card(10, None, 111, level=4, category="task", intensity="light")
    assert service.set_level_4_consent(10, None, 111, True) is False
    assert service.set_level_4_consent(10, None, 222, True) is True
    with pytest.raises(NoCardsAvailable):
        service.draw_card(10, None, 111, level=4, category="task", intensity="light")
    db.close()


def test_hard_consent_records_safety_event(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)
    service.set_hard_consent(10, None, 111, True)
    service.set_hard_consent(10, None, 222, True)
    event = db.fetchone("SELECT * FROM safety_events WHERE event_type = 'hard_enabled'")
    assert event is not None
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
    db.close()


def test_single_account_mode_uses_virtual_player_slots(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_single_account_config(tmp_path))
    service.ensure_session(10, None)
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


def test_restricted_cards_require_session_unlock(tmp_path):
    db = migrated_db(tmp_path)
    import_restricted_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(10, None)
    service.accept_base_consent(10, None, 111)
    service.accept_base_consent(10, None, 222)

    with pytest.raises(NoCardsAvailable):
        service.draw_card(10, None, 111, level=2, category="task", intensity="light")

    service.unlock_restricted_content(10, None)
    result = service.draw_card(10, None, 111, level=2, category="task", intensity="light")
    assert result.card.external_id.startswith("restricted_")
    db.close()
