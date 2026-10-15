"""Hidden three-player game: admin switch, group only, separate deck."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.handlers import admin_threesome, common
from app.keyboards.admin import admin_menu
from app.services import group_access, threesome
from app.services.game_service import GameService
from tests.helpers import import_seed, make_config, migrated_db
from tests.test_ux_polish import FakeBot, _datas

GROUP = -1009876543210
HUSBAND, WIFE, GUEST = 555, 666, 777


class CrowdedBot(FakeBot):
    def __init__(self, members):
        super().__init__()
        self.members = members

    async def get_chat_member_count(self, chat_id):
        return self.members


@pytest.fixture(autouse=True)
def _reset():
    yield
    threesome.registry = None
    group_access.registry = None


def _setup(tmp_path, enabled=True):
    db = migrated_db(tmp_path)
    import_seed(db)
    service = GameService(db, make_config(tmp_path))
    threesome.registry = service.threesome
    group_access.registry = service.groups
    service.threesome.set_enabled(enabled, HUSBAND)
    service.groups.unlock(GROUP, HUSBAND)
    need = service.players_needed()
    for uid, name in ((HUSBAND, "Никита"), (WIFE, "Аня"), (GUEST, "Лена"))[:need]:
        service.groups.join(GROUP, uid, name, need)
    return db, service


def test_switch_lives_only_in_the_admin_menu():
    assert "three:menu" in _datas(admin_menu())


def test_three_players_take_turns_with_their_names(tmp_path):
    db, service = _setup(tmp_path)
    session = service.ensure_session(GROUP, None)
    assert session["play_mode"] == "threesome" and int(session["player_3_id"]) == GUEST
    names = []
    for _ in range(6):
        status = service.status(GROUP, None)
        names.append(status["current_player_label"])
        player = int(status["current_player_id"])
        result = service.draw_card(GROUP, None, player, level=3, category=None)
        assert result.card.external_id.startswith("three_")
        service.finish_turn(GROUP, None, player)
    assert names == ["Никита", "Аня", "Лена"] * 2


def test_couple_games_never_get_threesome_cards(tmp_path):
    db, service = _setup(tmp_path, enabled=False)
    service.ensure_session(GROUP, None)
    for i in range(60):
        player = int(service.status(GROUP, None)["current_player_id"])
        result = service.draw_card(GROUP, None, player, level=None, category=None, source="roulette")
        assert not result.card.external_id.startswith("three_")
        service.finish_turn(GROUP, None, player)


def test_turning_the_mode_off_restarts_the_group_game_for_two(tmp_path):
    db, service = _setup(tmp_path)
    first = service.ensure_session(GROUP, None)
    service.threesome.set_enabled(False, HUSBAND)
    second = service.ensure_session(GROUP, None)
    assert second["id"] != first["id"] and second["player_3_id"] is None


def test_group_of_three_people_is_allowed_only_in_threesome_mode(tmp_path):
    db, service = _setup(tmp_path, enabled=False)
    chat = SimpleNamespace(id=GROUP, type="supergroup")
    assert asyncio.run(common.group_has_strangers(CrowdedBot(4), chat))
    service.threesome.set_enabled(True, HUSBAND)
    assert not asyncio.run(common.group_has_strangers(CrowdedBot(4), chat))
    assert asyncio.run(common.group_has_strangers(CrowdedBot(5), chat))


def test_admin_screen_has_only_the_switch(tmp_path):
    db, service = _setup(tmp_path)
    state = service.threesome.state()
    assert "включён" in admin_threesome.threesome_text(state)
    assert _datas(admin_threesome.threesome_menu(state)) == ["three:toggle", "admin:menu"]
