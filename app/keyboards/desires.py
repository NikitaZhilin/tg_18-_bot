from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def desire_list(rows, *, page: int, total: int, player_label) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{player_label(str(row['owner_slot']))}: {row['title'] or 'Желание'}",
                callback_data=f"game:desire:{row['id']}:{page}",
            )
        ]
        for row in rows
    ]
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="←", callback_data=f"game:desires:{page - 1}"))
    if (page + 1) * 10 < total:
        navigation.append(InlineKeyboardButton(text="→", callback_data=f"game:desires:{page + 1}"))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text="В меню", callback_data="game:home")])
    buttons.append([InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def desire_actions(desire_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Использовать желание", callback_data=f"game:desire_use:{desire_id}")],
            [InlineKeyboardButton(text="Назад к желаниям", callback_data=f"game:desires:{page}")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
            [InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")],
        ]
    )
