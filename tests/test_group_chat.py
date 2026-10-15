"""Playing in a shared Telegram group: two accounts, one game, strict turns."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.handlers import game
from app.services.game_service import GameService
from tests.helpers import import_seed, make_config, migrated_db
from tests.test_ux_polish import FakeBot, FakeCallback, FakeMessage

GROUP = -1009876543210
HUSBAND, WIFE, STRANGER = 111, 222, 999


def _group_message():
    message = FakeMessage()
    message.chat = SimpleNamespace(id=GROUP, title="Мы", type="supergroup")
    return message


def _setup(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_config(tmp_path)
    service = GameService(db, config)
    bot = FakeBot()
    return db, config, service, bot


def _press(data, user, config, service, bot, handler):
    callback = FakeCallback(data, user_id=user, message=_group_message(), bot=bot)
    asyncio.run(handler(callback, config, service))
    return callback


def test_group_game_has_two_different_players(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    session = service.ensure_session(GROUP, None, "Мы")
    assert {int(session["player_1_id"]), int(session["player_2_id"])} == {HUSBAND, WIFE}


def test_turns_alternate_between_two_accounts_in_a_group(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    first = _press("game:roulette", HUSBAND, config, service, bot, game.cb_roulette)
    turn_id = service.status(GROUP, None)["active_turn_id"]
    assert turn_id and not any(alert for _, alert in first.answers)

    # The wife cannot draw or close the husband's card.
    blocked = _press("game:roulette", WIFE, config, service, bot, game.cb_roulette)
    assert any(alert for _, alert in blocked.answers)
    blocked_done = _press(f"game:done:{turn_id}", WIFE, config, service, bot, game.cb_done)
    assert any(alert for _, alert in blocked_done.answers)
    assert service.status(GROUP, None)["active_turn_id"] == turn_id

    _press(f"game:done:{turn_id}", HUSBAND, config, service, bot, game.cb_done)
    assert int(service.status(GROUP, None)["current_player_id"]) == WIFE
    hers = _press("game:roulette", WIFE, config, service, bot, game.cb_roulette)
    assert not any(alert for _, alert in hers.answers)


def test_stranger_in_the_group_cannot_press_anything(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    callback = _press("game:roulette", STRANGER, config, service, bot, game.cb_roulette)
    assert callback.answers == [("Доступ закрыт", True)]
    assert service.active_session(GROUP, None) is None


def test_group_game_is_separate_from_the_private_one(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    service.ensure_session(HUSBAND, None)
    service.set_anal_mode(HUSBAND, None, "off")
    service.ensure_session(GROUP, None, "Мы")
    assert service.anal_mode(GROUP, None) == "both"
    assert service.active_session(GROUP, None)["id"] != service.active_session(HUSBAND, None)["id"]


def test_truth_or_dare_in_a_group_passes_the_choice_to_the_wife(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    _press("tod:draw:2:light:task", HUSBAND, config, service, bot, game.cb_tod_draw)
    turn_id = service.status(GROUP, None)["active_turn_id"]
    _press(f"game:done:{turn_id}", HUSBAND, config, service, bot, game.cb_done)
    chat_id, text, _ = bot.sent[-1]
    assert chat_id == GROUP and "Ходит: B" in text
