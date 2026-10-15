"""Playing in a group: password, «🙋 Я играю», strict turns. Private chats unchanged."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.handlers import common, game, group_play, membership
from app.services import group_access
from app.services.game_service import GameService
from tests.helpers import import_seed, make_config, migrated_db
from tests.test_ux_polish import FakeBot, FakeCallback, FakeMessage

GROUP = -1009876543210
HUSBAND, WIFE, STRANGER = 555, 666, 999


@pytest.fixture(autouse=True)
def _reset_registry():
    yield
    group_access.registry = None


def _group_message(user_id=HUSBAND, text="", reply_to=None):
    message = FakeMessage(text)
    message.chat = SimpleNamespace(id=GROUP, title="Мы", type="supergroup")
    message.from_user = SimpleNamespace(id=user_id, first_name={HUSBAND: "Никита", WIFE: "Аня"}.get(user_id, "Гость"), username=None)
    message.reply_to_message = reply_to
    message.answers = []
    message.deleted = False

    async def answer(text, reply_markup=None, **kwargs):
        message.answers.append((text, reply_markup))

    async def delete():
        message.deleted = True

    message.answer = answer
    message.delete = delete
    message.bot = FakeBot()
    return message


def _setup(tmp_path, unlocked=True, joined=(HUSBAND, WIFE)):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_config(tmp_path)
    service = GameService(db, config)
    group_access.registry = service.groups
    service.groups.set_password("04101996", 111)
    if unlocked:
        service.groups.unlock(GROUP, HUSBAND)
    for uid in joined:
        service.groups.join(GROUP, uid, {HUSBAND: "Никита", WIFE: "Аня"}[uid], 2)
    return db, config, service, FakeBot()


def _press(data, user, config, service, bot, handler):
    callback = FakeCallback(data, user_id=user, message=_group_message(user), bot=bot)
    callback.from_user = SimpleNamespace(id=user, first_name={HUSBAND: "Никита", WIFE: "Аня"}.get(user, "Гость"), username=None)
    asyncio.run(handler(callback, config, service))
    return callback


def test_locked_group_asks_for_the_password_and_opens_with_it(tmp_path):
    db, config, service, bot = _setup(tmp_path, unlocked=False, joined=())
    start = _group_message()
    asyncio.run(group_play.start_in_group(start, config, service))
    assert start.answers[0][0].startswith("🔒 Эта группа закрыта")

    prompt = SimpleNamespace(text=start.answers[0][0], from_user=SimpleNamespace(is_bot=True))
    wrong = _group_message(text="1234", reply_to=prompt)
    asyncio.run(group_play.msg_password(wrong, config, service))
    assert not service.groups.is_unlocked(GROUP) and wrong.deleted

    right = _group_message(text="04101996", reply_to=prompt)
    asyncio.run(group_play.msg_password(right, config, service))
    assert service.groups.is_unlocked(GROUP) and right.deleted
    assert "Я играю" in right.answers[0][0]


def test_password_is_not_stored_in_plain_text(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    stored = db.fetchone("SELECT value FROM bot_settings WHERE key = 'group_password'")["value"]
    assert "04101996" not in stored and stored.startswith("pbkdf2$")


def test_nothing_works_in_a_locked_group(tmp_path):
    db, config, service, bot = _setup(tmp_path, unlocked=False, joined=())
    callback = _press("game:roulette", HUSBAND, config, service, bot, game.cb_roulette)
    assert callback.answers[0][0] == common.GROUP_LOCKED_TEXT


def test_players_join_and_get_their_names(tmp_path):
    db, config, service, bot = _setup(tmp_path, joined=())
    _press("grp:join", HUSBAND, config, service, bot, group_play.cb_join)
    assert service.active_session(GROUP, None) is None  # waiting for the second
    _press("grp:join", WIFE, config, service, bot, group_play.cb_join)
    status = service.status(GROUP, None)
    assert status["active"] and status["current_player_label"] == "Никита"
    full = _press("grp:join", STRANGER, config, service, bot, group_play.cb_join)
    assert any("заняты" in (text or "") for text, _ in full.answers)


def test_turns_alternate_between_two_phones(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    service.ensure_session(GROUP, None)
    _press("game:roulette", HUSBAND, config, service, bot, game.cb_roulette)
    turn_id = service.status(GROUP, None)["active_turn_id"]
    blocked = _press("game:roulette", WIFE, config, service, bot, game.cb_roulette)
    assert any(alert for _, alert in blocked.answers)
    _press(f"game:done:{turn_id}", HUSBAND, config, service, bot, game.cb_done)
    assert int(service.status(GROUP, None)["current_player_id"]) == WIFE
    assert bot.sent[-1][1].startswith("✅ Готово! Теперь очередь: Аня")


def test_someone_not_in_the_game_cannot_press(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    callback = _press("game:roulette", STRANGER, config, service, bot, game.cb_roulette)
    assert callback.answers[0][0] == common.NOT_IN_GAME_TEXT


def test_private_chat_is_one_phone_for_both(tmp_path):
    db, config, service, bot = _setup(tmp_path)
    session = service.ensure_session(111, None)
    assert int(session["player_1_id"]) == int(session["player_2_id"]) == 111


def test_ending_the_group_game_frees_the_seats(tmp_path):
    from app.services.safety_service import SafetyService

    db, config, service, bot = _setup(tmp_path)
    service.ensure_session(GROUP, None)
    SafetyService(db).end_game(GROUP, None, HUSBAND)
    assert service.groups.roster(GROUP) == []


def test_bot_greets_whoever_adds_it(tmp_path):
    config = make_config(tmp_path)
    bot = FakeBot()
    event = SimpleNamespace(
        chat=SimpleNamespace(id=GROUP, type="supergroup"),
        new_chat_member=SimpleNamespace(status="member"),
        from_user=SimpleNamespace(id=STRANGER),
        bot=bot,
    )
    asyncio.run(membership.on_bot_membership(event, config))
    assert "пароль" in bot.sent[0][1]
