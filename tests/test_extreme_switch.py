from __future__ import annotations

import pytest

from app.keyboards.game import main_menu
from app.services.errors import GameError
from app.services.game_service import GameService
from tests.helpers import import_restricted_seed, import_seed, make_config, migrated_db
from tests.test_ux_polish import _datas, _texts

CHAT = 111  # private chat: one phone for both


def _service(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    import_restricted_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(CHAT, None)
    return db, service


def _draw_all_level4(service):
    ids = []
    while True:
        try:
            result = service.draw_card(CHAT, None, CHAT, level=4, category=None, intensity="hard")
        except Exception:
            return ids
        ids.append(result.card.external_id)
        service.finish_turn(CHAT, None, CHAT)


def test_extreme_is_on_by_default_and_mixes_into_regular_draws(tmp_path):
    db, service = _service(tmp_path)
    assert service.status(CHAT, None)["restricted_content"]
    assert any(card_id.startswith("extreme_v2_") for card_id in _draw_all_level4(service))


def test_switching_extreme_off_hides_its_cards_everywhere(tmp_path):
    db, service = _service(tmp_path)
    assert service.toggle_extreme(CHAT, None) is False
    assert not any(card_id.startswith("extreme_v2_") for card_id in _draw_all_level4(service))
    with pytest.raises(GameError, match="Экстрим"):
        service.draw_card(CHAT, None, CHAT, level=None, category=None, collection_code="restricted_content")
    assert service.toggle_extreme(CHAT, None) is True


def test_menu_shows_the_switch_and_the_extreme_button_only_when_on():
    on = main_menu(restricted_enabled=True)
    off = main_menu(restricted_enabled=False)
    assert "🔞 Экстрим: ✅ вкл" in _texts(on) and "game:extreme" in _datas(on)
    assert "🔞 Экстрим: 🚫 выкл" in _texts(off) and "game:extreme" not in _datas(off)
    assert "game:extreme_toggle" not in _datas(main_menu(extreme_switch=False))
