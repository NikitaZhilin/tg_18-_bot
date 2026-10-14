from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.handlers import errors
from app.services.error_report import ReportThrottle, USER_ERROR_TEXT
from tests.helpers import make_config


class FakeCallback:
    data = "admin:card:not-a-number"

    def __init__(self):
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append((chat_id, text, parse_mode))


def _event(callback):
    update = SimpleNamespace(callback_query=callback, message=None, event_type="callback_query")
    return SimpleNamespace(update=update, exception=ValueError("invalid literal for int()"))


def test_broken_button_gets_an_answer_and_owners_get_one_report(tmp_path, monkeypatch):
    monkeypatch.setattr(errors, "_throttle", ReportThrottle())
    callback, bot = FakeCallback(), FakeBot()
    config = make_config(tmp_path)

    assert asyncio.run(errors.on_error(_event(callback), bot, config)) is True
    assert callback.answers == [(USER_ERROR_TEXT, True)]
    assert sorted(chat_id for chat_id, _, _ in bot.sent) == [111, 222]
    assert all(parse_mode is None for _, _, parse_mode in bot.sent)

    asyncio.run(errors.on_error(_event(FakeCallback()), bot, config))
    assert len(bot.sent) == 2  # repeated error is not re-sent within the window
