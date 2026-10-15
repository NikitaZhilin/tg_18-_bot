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


# --- private chat stays a one-phone game; group guards ----------------------


def test_private_chat_is_one_phone_for_both_even_with_two_accounts(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    session = service.ensure_session(HUSBAND, None)
    assert int(session["player_1_id"]) == int(session["player_2_id"]) == HUSBAND
    first = service.draw_card(HUSBAND, None, HUSBAND, level=1, category="task")
    assert service.finish_turn(HUSBAND, None, HUSBAND) == "B"
    service.draw_card(HUSBAND, None, HUSBAND, level=1, category="task")  # the «second player» on the same phone
    assert first.turn_id


def test_wife_has_her_own_one_phone_game_in_her_private_chat(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    session = service.ensure_session(WIFE, None)
    assert int(session["player_1_id"]) == int(session["player_2_id"]) == WIFE


def test_group_needs_two_accounts(tmp_path):
    import pytest
    from dataclasses import replace

    from app.services.errors import GameError

    db = migrated_db(tmp_path)
    config = replace(make_config(tmp_path), allowed_user_ids={HUSBAND}, admin_user_ids={HUSBAND}, single_account_two_players=True)
    service = GameService(db, config)
    assert service.ensure_session(HUSBAND, None)  # private chat still works
    session = service.ensure_session(GROUP, None)
    assert int(session["player_1_id"]) == HUSBAND  # alone in a group: same as private


class CrowdedBot(FakeBot):
    def __init__(self, members):
        super().__init__()
        self.members = members
        self.left = []

    async def get_chat_member_count(self, chat_id):
        return self.members

    async def leave_chat(self, chat_id):
        self.left.append(chat_id)


def test_no_cards_in_a_group_with_a_third_person(tmp_path):
    db, config, service, _ = _setup(tmp_path)
    bot = CrowdedBot(members=4)
    callback = _press("game:roulette", HUSBAND, config, service, bot, game.cb_roulette)
    assert callback.answers and "кроме вас двоих" in callback.answers[0][0]
    assert service.active_session(GROUP, None) is None


def test_bot_leaves_a_group_added_by_a_stranger_and_greets_partners(tmp_path):
    from app.handlers import membership

    config = make_config(tmp_path)

    def event(by, bot):
        return SimpleNamespace(
            chat=SimpleNamespace(id=GROUP, type="supergroup"),
            new_chat_member=SimpleNamespace(status="member"),
            from_user=SimpleNamespace(id=by),
            bot=bot,
        )

    stranger_bot = CrowdedBot(members=3)
    asyncio.run(membership.on_bot_membership(event(STRANGER, stranger_bot), config))
    assert stranger_bot.left == [GROUP] and stranger_bot.sent == []

    our_bot = CrowdedBot(members=3)
    asyncio.run(membership.on_bot_membership(event(HUSBAND, our_bot), config))
    assert our_bot.left == [] and "/start" in our_bot.sent[0][1]
