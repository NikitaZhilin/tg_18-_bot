from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

from aiogram.fsm.storage.base import StorageKey

from app.handlers import fallback
from app.handlers.admin_states import AdminAddCard
from app.main import build_dispatcher
from app.storage.fsm import SQLiteFSMStorage
from tests.helpers import make_config, migrated_db

KEY = StorageKey(bot_id=1, chat_id=111, user_id=111)


def test_fresh_admin_dialog_is_kept(tmp_path):
    storage = SQLiteFSMStorage(migrated_db(tmp_path))
    asyncio.run(storage.set_state(KEY, AdminAddCard.title))
    assert asyncio.run(storage.get_state(KEY)) == AdminAddCard.title.state


def test_admin_dialog_left_for_days_is_forgotten(tmp_path):
    db = migrated_db(tmp_path)
    storage = SQLiteFSMStorage(db)
    asyncio.run(storage.set_state(KEY, AdminAddCard.restricted_password))
    asyncio.run(storage.set_data(KEY, {"level": 2}))
    db.execute("UPDATE fsm_states SET updated_at = datetime('now', '-3 days')")

    # A message typed days later must not be taken as the password / card title.
    assert asyncio.run(storage.get_state(KEY)) is None
    assert asyncio.run(storage.get_data(KEY)) == {}


class FakeCallback:
    def __init__(self, data):
        self.data = data
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))


def test_stale_button_gets_an_answer_instead_of_spinner():
    callback = FakeCallback("old:removed:button")
    asyncio.run(fallback.cb_stale_button(callback))
    assert callback.answers == [(fallback.STALE_BUTTON_TEXT, True)]


class FakeMessage:
    def __init__(self, user_id, chat_type="private"):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(type=chat_type)
        self.sent = []

    async def answer(self, text, **kwargs):
        self.sent.append(text)


def test_unknown_message_hint_only_for_allowed_users_in_private(tmp_path):
    config = make_config(tmp_path)
    allowed, stranger, group = FakeMessage(111), FakeMessage(999), FakeMessage(111, "group")
    for message in (allowed, stranger, group):
        asyncio.run(fallback.msg_unknown(message, config))
    assert allowed.sent == [fallback.UNKNOWN_MESSAGE_TEXT]
    assert stranger.sent == [] and group.sent == []


def test_fallback_router_is_registered_last():
    # Routers are module singletons and can join only one Dispatcher per process,
    # so check the registration order in the source instead of building another one.
    source = inspect.getsource(build_dispatcher)
    includes = [line.strip() for line in source.splitlines() if "include_router" in line]
    assert includes[-1] == "dp.include_router(fallback.router)"
