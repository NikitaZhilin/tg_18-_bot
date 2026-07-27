from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


ITEMS = [
    ("ice", "Лед"),
    ("oil", "Масло"),
    ("rope", "Веревка"),
    ("blindfold", "Повязка"),
    ("vibrator", "Вибратор"),
    ("headphones", "Наушники"),
    ("candle", "Свеча"),
    ("clamps", "Зажимы"),
    ("food", "Еда"),
]


def inventory_menu(selected: set[str] | None = None) -> InlineKeyboardMarkup:
    selected = selected or set()
    rows = []
    for code, name in ITEMS:
        mark = "✓ " if code in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{name}", callback_data=f"inv:toggle:{code}")])
    rows.append([InlineKeyboardButton(text="Сохранить", callback_data="inv:save")])
    rows.append([InlineKeyboardButton(text="В меню", callback_data="game:menu")])
    rows.append([InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
