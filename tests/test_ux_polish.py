from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText

from app.handlers import game, safety, start
from app.handlers.screens import show_screen
from app.keyboards.game import card_actions, category_menu, main_menu
from app.services.game_service import GameService
from app.services.safety_service import SafetyService
from tests.helpers import import_seed, make_config, migrated_db

CHAT = -100


def _datas(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _texts(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


# --- keyboards -------------------------------------------------------------


def test_main_menu_is_compact_and_admin_only_for_owners():
    player = main_menu()
    owner = main_menu(show_admin=True)
    assert "admin:menu" not in _datas(player)
    assert "admin:menu" in _datas(owner)
    assert "game:settings" in _datas(player)
    for moved in ("inv:menu", "boundaries:menu", "game:default_levels"):
        assert moved not in _datas(player)


def test_category_menu_shows_only_categories_with_cards():
    texts = _texts(category_menu(3, "hard", ["pose", "task"]))
    assert "🛏 Поза" in texts and "🎯 Задание" in texts
    assert "💬 Вопрос" not in texts and "🎁 Желание" not in texts


def test_card_buttons_are_bound_to_the_card():
    datas = _datas(card_actions(42, has_timer=True))
    assert {"game:timer:42", "game:done:42", "game:refuse:42", "game:revision:42"} <= set(datas)


# --- fakes -----------------------------------------------------------------


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.sent.append((chat_id, text, reply_markup))


class FakeMessage:
    def __init__(self, text="", reply_markup=None, fail_edit=None):
        self.chat = SimpleNamespace(id=CHAT, title=None)
        self.text = text
        self.reply_markup = reply_markup
        self.message_thread_id = None
        self.fail_edit = fail_edit
        self.edits = []

    async def edit_text(self, text, reply_markup=None):
        if self.fail_edit:
            raise TelegramBadRequest(
                method=EditMessageText(text=text), message=f"Bad Request: {self.fail_edit}"
            )
        self.edits.append((text, reply_markup))
        self.text, self.reply_markup = text, reply_markup

    async def edit_reply_markup(self, reply_markup=None):
        self.reply_markup = reply_markup


class FakeCallback:
    def __init__(self, data, user_id=111, message=None, bot=None):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message or FakeMessage()
        self.bot = bot or FakeBot()
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))


def _ready_game(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_config(tmp_path)
    service = GameService(db, config)
    service.ensure_session(CHAT, None)
    service.accept_base_consent(CHAT, None, 111)
    service.accept_base_consent(CHAT, None, 222)
    return db, config, service, SafetyService(db)


# --- screens ----------------------------------------------------------------


def test_menu_navigation_edits_the_pressed_message():
    callback = FakeCallback("game:menu")
    asyncio.run(show_screen(callback, "Выберите уровень:", main_menu()))
    assert callback.message.edits and callback.bot.sent == []


def test_not_editable_message_falls_back_to_a_new_one():
    callback = FakeCallback("game:menu", message=FakeMessage(fail_edit="message can't be edited"))
    asyncio.run(show_screen(callback, "Меню", main_menu()))
    assert callback.bot.sent and callback.bot.sent[0][1] == "Меню"


def test_unchanged_screen_is_not_duplicated():
    callback = FakeCallback("game:home", message=FakeMessage(fail_edit="message is not modified"))
    asyncio.run(show_screen(callback, "Меню", main_menu()))
    assert callback.bot.sent == []


# --- game flow ---------------------------------------------------------------


def test_done_closes_the_card_and_opens_menu_below(tmp_path):
    db, config, service, _ = _ready_game(tmp_path)
    result = service.draw_card(CHAT, None, 111, level=1, category="task", intensity="light")
    card_message = FakeMessage("Карточка", card_actions(result.turn_id, False))
    callback = FakeCallback(f"game:done:{result.turn_id}", message=card_message)

    asyncio.run(game.cb_done(callback, config, service))

    assert card_message.reply_markup is None and card_message.text.endswith("✅ Сделано")
    assert "очередь: B" in callback.bot.sent[0][1]
    assert service.status(CHAT, None)["has_active_turn"] is False


def test_old_card_buttons_do_not_touch_the_open_card(tmp_path):
    db, config, service, _ = _ready_game(tmp_path)
    old = service.draw_card(CHAT, None, 111, level=1, category="task", intensity="light")
    service.finish_turn(CHAT, None, 111)
    current = service.draw_card(CHAT, None, 222, level=1, category="task", intensity="light")

    callback = FakeCallback(f"game:replace:{old.turn_id}", user_id=222)
    asyncio.run(game.cb_replace_card(callback, config, service, SafetyService(db)))

    assert callback.answers[-1] == (game.CARD_CLOSED_TEXT, True)
    assert service.status(CHAT, None)["active_turn_id"] == current.turn_id


def test_end_game_asks_first_and_is_not_a_stopword(tmp_path):
    db, config, service, safety_service = _ready_game(tmp_path)
    ask = FakeCallback("safe:end_game")
    asyncio.run(safety.cb_end_game_ask(ask, config))
    assert service.active_session(CHAT, None) is not None  # nothing ended yet
    assert "safe:end_game:yes" in _datas(ask.bot.sent[0][2])

    confirm = FakeCallback("safe:end_game:yes")
    asyncio.run(safety.cb_end_game(confirm, config, safety_service, service))
    row = db.fetchone("SELECT status, stop_reason FROM sessions ORDER BY id DESC LIMIT 1")
    assert (row["status"], row["stop_reason"]) == ("completed", "end_game")
    assert db.fetchone("SELECT COUNT(*) AS c FROM safety_events")["c"] == 0


def test_old_reset_confirmation_button_works(tmp_path):
    # Used to fail with NameError: main_menu was not imported in game.py.
    db, config, service, safety_service = _ready_game(tmp_path)
    callback = FakeCallback("game:reset:yes")
    asyncio.run(game.cb_reset_yes(callback, config, service, safety_service))
    assert service.active_session(CHAT, None) is None
    assert callback.message.edits[-1][0].startswith("Игра завершена.")


# --- help --------------------------------------------------------------------


class HelpMessage:
    def __init__(self, user_id):
        self.from_user = SimpleNamespace(id=user_id)
        self.sent = []

    async def answer(self, text, **kwargs):
        self.sent.append(text)


def test_help_hides_owner_commands_from_partner(tmp_path):
    config = replace(make_config(tmp_path), admin_user_ids={111})
    owner, partner = HelpMessage(111), HelpMessage(222)
    asyncio.run(start.cmd_help(owner, config))
    asyncio.run(start.cmd_help(partner, config))
    assert "/admin" in owner.sent[0]
    assert "/admin" not in partner.sent[0] and "/stopword" in partner.sent[0]


def test_menu_screens_explain_levels_intensity_and_categories():
    from app.keyboards.game import category_menu_text, intensity_menu_text, level_menu_text

    levels = level_menu_text()
    for name in ("Флирт", "Разогрев", "Секс", "БДСМ"):
        assert name in levels
    assert "связывание" in levels
    assert "🌿 Мягко" in intensity_menu_text(3) and "💥 Жёстко" in intensity_menu_text(3)
    text = category_menu_text(4, "hard", ["task", "pose"])
    assert "🎯 Задание" in text and "🛏 Поза" in text and "💬 Вопрос" not in text


def test_cards_have_no_generic_aftercare_footer(tmp_path):
    db, config, service, _ = _ready_game(tmp_path)
    result = service.draw_card(CHAT, None, 111, level=4, category="task", intensity="hard")
    from app.services.game_service import format_card

    assert "💛" not in format_card(result.card)
