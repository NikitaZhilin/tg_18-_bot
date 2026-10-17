from __future__ import annotations

import asyncio

from app.handlers import game
from app.keyboards.admin import admin_menu
from app.keyboards.game import card_actions, main_menu
from app.services.game_service import GameService
from app.services.safety_service import SafetyService
from tests.helpers import import_restricted_seed, import_seed, make_config, migrated_db
from tests.test_ux_polish import FakeBot, FakeCallback, FakeMessage, _datas, _texts

CHAT = 111


def _service(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    import_restricted_seed(db)
    service = GameService(db, make_config(tmp_path))
    service.ensure_session(CHAT, None)
    return db, service


def test_next_game_keeps_settings_and_unused_desires(tmp_path):
    db, service = _service(tmp_path)
    service.set_anal_mode(CHAT, None, "her")
    service.toggle_extreme(CHAT, None)
    service.set_enabled_level(CHAT, None, 1, False)
    service.set_items_for_active_session(CHAT, None, {"rope": 3})
    service.draw_card(CHAT, None, CHAT, level=2, category="desire")
    service.finish_turn(CHAT, None, CHAT)
    SafetyService(db).end_game(CHAT, None, CHAT)

    service.ensure_session(CHAT, None)
    status = service.status(CHAT, None)
    assert status["anal_mode"] == "her"
    assert status["restricted_content"] is False
    assert 1 not in status["enabled_levels"]
    assert service.items_for_active_session(CHAT, None) == {"rope": 3}
    assert status["saved_desires"] == 1


def test_favorite_card_can_be_played_again(tmp_path):
    db, service = _service(tmp_path)
    first = service.draw_card(CHAT, None, CHAT, level=3, category="task")
    assert service.toggle_favorite(CHAT, None, first.turn_id) is True
    service.finish_turn(CHAT, None, CHAT)
    favorite = service.favorites(CHAT, None)[0]
    again = service.draw_card(CHAT, None, CHAT, level=None, category=None, card_id=favorite["id"])
    assert again.card.id == first.card.id
    assert service.toggle_favorite(CHAT, None, again.turn_id) is False
    assert service.favorites(CHAT, None) == []


def test_favorites_button_in_menu_and_on_cards():
    assert "game:favs:0" in _datas(main_menu())
    assert "⭐ Избранное (3)" in _texts(main_menu(favorites=3))
    assert "game:fav:7" in _datas(card_actions(7, False))
    assert "game:fav:7" not in _datas(card_actions(7, False, is_penalty=True))


def test_end_of_the_evening_summary(tmp_path):
    db, service = _service(tmp_path)
    for _ in range(2):
        service.draw_card(CHAT, None, CHAT, level=3, category="task")
        service.finish_turn(CHAT, None, CHAT)
    refused = service.draw_card(CHAT, None, CHAT, level=2, category="task")
    service.refuse_card(CHAT, None, CHAT, refused.turn_id)
    service.finish_turn(CHAT, None, CHAT)
    summary = service.session_summary(int(service.active_session(CHAT, None)["id"]))
    assert "карточек сыграно — 2" in summary and "Секс — 2" in summary and "Отказов — 1" in summary


def test_admin_buttons_show_counts():
    texts = _texts(admin_menu(counts={"feedback": 2, "conflicts": 12, "revision": 0}))
    assert "Сообщения игроков (2)" in texts and "Конфликты обновлений (12)" in texts
    assert "Карточки на доработке" in texts
