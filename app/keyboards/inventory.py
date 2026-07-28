from __future__ import annotations

from collections.abc import Sequence
from typing import Mapping

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


FREQUENCY_LABELS = {
    0: "выключен",
    1: "редко",
    2: "иногда",
    3: "часто",
}


def inventory_menu(items: Sequence[Mapping[str, object]], selected: dict[str, int] | None = None) -> InlineKeyboardMarkup:
    selected = selected or {}
    rows = []
    for item in items:
        code = str(item["code"])
        name = str(item["name"])
        frequency = int(selected.get(code, 0))
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{name}: {FREQUENCY_LABELS[frequency]}",
                    callback_data=f"inv:toggle:{code}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Сохранить", callback_data="inv:save")])
    rows.append([InlineKeyboardButton(text="В меню", callback_data="game:home")])
    rows.append([InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
