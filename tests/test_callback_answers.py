from __future__ import annotations

import asyncio

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery

from app.handlers.common import answer_callback


class ExpiredCallback:
    async def answer(self, *args, **kwargs):
        raise TelegramBadRequest(
            method=AnswerCallbackQuery(callback_query_id="expired"),
            message="Bad Request: query is too old and response timeout expired or query ID is invalid",
        )


class BrokenCallback:
    async def answer(self, *args, **kwargs):
        raise TelegramBadRequest(
            method=AnswerCallbackQuery(callback_query_id="broken"),
            message="Bad Request: another callback error",
        )


def test_expired_callback_answer_is_ignored():
    asyncio.run(answer_callback(ExpiredCallback()))


def test_other_callback_errors_are_not_hidden():
    with pytest.raises(TelegramBadRequest):
        asyncio.run(answer_callback(BrokenCallback()))
