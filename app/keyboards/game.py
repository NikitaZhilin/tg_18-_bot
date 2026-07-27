from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать/продолжить", callback_data="game:menu")],
            [InlineKeyboardButton(text="Русская рулетка", callback_data="game:roulette")],
            [InlineKeyboardButton(text="Настройки реквизита", callback_data="inv:menu")],
            [InlineKeyboardButton(text="Границы на сегодня", callback_data="boundaries:menu")],
            [InlineKeyboardButton(text="Админка", callback_data="admin:menu")],
            [InlineKeyboardButton(text="Включить уровень 4", callback_data="game:level4")],
            [InlineKeyboardButton(text="Включить hard", callback_data="game:hard")],
            [InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")],
        ]
    )


def consent_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтверждаю", callback_data="game:base_consent")],
            [InlineKeyboardButton(text="Отмена", callback_data="safe:stopword")],
        ]
    )


def level_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="game:level:1"),
                InlineKeyboardButton(text="2", callback_data="game:level:2"),
                InlineKeyboardButton(text="3", callback_data="game:level:3"),
                InlineKeyboardButton(text="4", callback_data="game:level:4"),
            ],
            [InlineKeyboardButton(text="Русская рулетка", callback_data="game:roulette")],
            [InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")],
        ]
    )


def intensity_menu(level: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Легкие", callback_data=f"game:intensity:{level}:light"),
                InlineKeyboardButton(text="Средние", callback_data=f"game:intensity:{level}:medium"),
                InlineKeyboardButton(text="Жесткие", callback_data=f"game:intensity:{level}:hard"),
            ],
            [InlineKeyboardButton(text="Назад", callback_data="game:menu")],
            [InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")],
        ]
    )


def category_menu(level: int, intensity: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Вопрос", callback_data=f"game:category:{level}:{intensity}:question"),
                InlineKeyboardButton(text="Задание", callback_data=f"game:category:{level}:{intensity}:task"),
            ],
            [
                InlineKeyboardButton(text="Поза", callback_data=f"game:category:{level}:{intensity}:pose"),
                InlineKeyboardButton(text="Желание", callback_data=f"game:category:{level}:{intensity}:desire"),
            ],
            [InlineKeyboardButton(text="Назад", callback_data=f"game:level:{level}")],
            [InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")],
        ]
    )


def card_actions(turn_id: int, has_timer: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_timer:
        rows.append([InlineKeyboardButton(text="Запустить таймер", callback_data=f"game:timer:{turn_id}")])
    rows.extend(
        [
            [
                InlineKeyboardButton(text="Готово", callback_data="game:done"),
                InlineKeyboardButton(text="Пропустить", callback_data="game:skip"),
            ],
            [InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reset_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, завершить", callback_data="game:reset:yes"),
                InlineKeyboardButton(text="Отмена", callback_data="game:reset:no"),
            ]
        ]
    )


BOUNDARY_OPTIONS = [
    ("no_quick_release_restraint", "Без фиксации"),
    ("unbounded_humiliation", "Без унижения"),
    ("injury", "Без боли/травм"),
    ("unsafe_wax", "Без воска"),
    ("sensory_deprivation", "Без сенсорных ограничений"),
    ("food", "Без еды/напитков"),
    ("toys", "Без игрушек"),
]


def boundary_menu(selected: set[str] | None = None) -> InlineKeyboardMarkup:
    selected = selected or set()
    rows = []
    for code, label in BOUNDARY_OPTIONS:
        mark = "✓ " if code in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"boundaries:toggle:{code}")])
    rows.append([InlineKeyboardButton(text="Сохранить", callback_data="boundaries:save")])
    rows.append([InlineKeyboardButton(text="В меню", callback_data="game:menu")])
    rows.append([InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
