from __future__ import annotations

import pytest

from app.services.card_picker import NoCardsAvailable
from app.services.game_service import GameError, GameService
from tests.helpers import import_seed, make_config, migrated_db


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
