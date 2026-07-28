from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def stopword_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
        ]
    )
