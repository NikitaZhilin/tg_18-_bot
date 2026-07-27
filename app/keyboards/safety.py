from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def stopword_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")]]
    )
