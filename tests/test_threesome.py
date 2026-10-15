"""Hidden three-player game: admin switch, group only, separate deck."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.handlers import admin_threesome, common, game
from app.keyboards.admin import admin_menu
from app.services import threesome
from app.services.game_service import GameService
from tests.helpers import import_seed, make_config, migrated_db
from tests.test_group_chat import CrowdedBot, GROUP, HUSBAND, WIFE, _group_message
from tests.test_ux_polish import FakeBot, FakeCallback, _datas

GUEST = 333


@pytest.fixture(autouse=True)
def _reset_registry():
    yield
    threesome.registry = None


def _setup(tmp_path, enabled=True):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_config(tmp_path)
    service = GameService(db, config)
    threesome.registry = service.threesome
    if enabled:
        service.threesome.set_third(GUEST, "Лена", HUSBAND)
        service.threesome.set_enabled(True, HUSBAND)
    return db, config, service


def test_switch_lives_only_in_the_admin_menu():
    assert "three:menu" in _datas(admin_menu())


def test_three_players_take_turns_in_a_group(tmp_path):
    db, config, service = _setup(tmp_path)
    session = service.ensure_session(GROUP, None)
    assert session["play_mode"] == "threesome" and int(session["player_3_id"]) == GUEST
    order = []
    for _ in range(6):
        player = int(service.status(GROUP, None)["current_player_id"])
        order.append(player)
        result = service.draw_card(GROUP, None, player, level=3, category=None)
        assert result.card.external_id.startswith("three_")
        service.finish_turn(GROUP, None, player)
    assert order == [HUSBAND, WIFE, GUEST, HUSBAND, WIFE, GUEST]


def test_couple_games_never_get_threesome_cards(tmp_path):
    db, config, service = _setup(tmp_path)
    service.ensure_session(HUSBAND, None)  # private chat: still the couple's deck
    for _ in range(60):
        result = service.draw_card(HUSBAND, None, HUSBAND, level=None, category=None, source="roulette")
        assert not result.card.external_id.startswith("three_")
        service.finish_turn(HUSBAND, None, HUSBAND)


def test_turning_the_mode_off_restarts_the_group_game_for_two(tmp_path):
    db, config, service = _setup(tmp_path)
    first = service.ensure_session(GROUP, None)
    service.threesome.set_enabled(False, HUSBAND)
    second = service.ensure_session(GROUP, None)
    assert second["id"] != first["id"] and second["player_3_id"] is None


def test_guest_may_play_only_in_the_group(tmp_path):
    db, config, service = _setup(tmp_path)
    group_chat = SimpleNamespace(id=GROUP, type="supergroup")
    private_chat = SimpleNamespace(id=GUEST, type="private")
    assert common.is_player(GUEST, config, group_chat)
    assert not common.is_player(GUEST, config, private_chat)
    service.threesome.set_enabled(False, HUSBAND)
    assert not common.is_player(GUEST, config, group_chat)


def test_group_of_three_people_is_allowed_only_in_threesome_mode(tmp_path):
    db, config, service = _setup(tmp_path, enabled=False)
    crowded = CrowdedBot(members=4)
    chat = SimpleNamespace(id=GROUP, type="supergroup")
    assert asyncio.run(common.group_has_strangers(crowded, chat))
    service.threesome.set_third(GUEST, "Лена", HUSBAND)
    service.threesome.set_enabled(True, HUSBAND)
    assert not asyncio.run(common.group_has_strangers(crowded, chat))
    assert asyncio.run(common.group_has_strangers(CrowdedBot(members=5), chat))


def test_guest_presses_buttons_in_the_group_on_her_turn(tmp_path):
    db, config, service = _setup(tmp_path)
    bot = FakeBot()
    for player in (HUSBAND, WIFE):
        callback = FakeCallback("game:roulette", user_id=player, message=_group_message(), bot=bot)
        asyncio.run(game.cb_roulette(callback, config, service))
        service.finish_turn(GROUP, None, player)
    hers = FakeCallback("game:roulette", user_id=GUEST, message=_group_message(), bot=bot)
    asyncio.run(game.cb_roulette(hers, config, service))
    assert not any(alert for _, alert in hers.answers)
    assert int(service.status(GROUP, None)["current_player_id"]) == GUEST


def test_admin_screen_shows_state_without_ids(tmp_path):
    db, config, service = _setup(tmp_path)
    text = admin_threesome.threesome_text(service.threesome.state())
    assert "включён" in text and "Лена" in text and str(GUEST) not in text
