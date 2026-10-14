from __future__ import annotations

from collections.abc import Sequence
from typing import Mapping

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


FREQUENCY_LABELS = {
    0: "нет",
    1: "есть · редко",
    2: "есть · иногда",
    3: "есть · часто",
}
FREQUENCY_MARKS = {0: "◻️", 1: "🟢", 2: "🟢", 3: "🟢"}


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
                    text=f"{FREQUENCY_MARKS[frequency]} {name} — {FREQUENCY_LABELS[frequency]}",
                    callback_data=f"inv:toggle:{code}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="inv:save")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="game:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
