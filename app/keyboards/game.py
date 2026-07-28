from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


LEVEL_LABELS = {
    1: "1 - Флирт",
    2: "2 - Разогрев",
    3: "3 - Секс",
    4: "4 - BDSM",
}


def main_menu(
    *,
    allow_level_4: bool = False,
    hard_enabled: bool = False,
    has_active_turn: bool = False,
) -> InlineKeyboardMarkup:
    rows = []
    if has_active_turn:
        rows.append([InlineKeyboardButton(text="Продолжить текущую карточку", callback_data="game:current")])
    rows.extend(
        [
            [InlineKeyboardButton(text="Выбрать карточку", callback_data="game:menu")],
            [InlineKeyboardButton(text="Русская рулетка", callback_data="game:roulette")],
            [InlineKeyboardButton(text="Настроить реквизит", callback_data="inv:menu")],
            [InlineKeyboardButton(text="Границы на сегодня", callback_data="boundaries:menu")],
            [InlineKeyboardButton(text="Админка", callback_data="admin:menu")],
            [
                InlineKeyboardButton(
                    text=f"Уровень 4: {'включен' if allow_level_4 else 'выключен'}",
                    callback_data="game:level4",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Жесткий режим: {'включен' if hard_enabled else 'выключен'}",
                    callback_data="game:hard",
                )
            ],
            [InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")],
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def consent_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтверждаю", callback_data="game:base_consent")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
        ]
    )


def level_menu(*, allow_level_4: bool = False) -> InlineKeyboardMarkup:
    level_rows = []
    for level, label in LEVEL_LABELS.items():
        if level == 4 and not allow_level_4:
            level_rows.append(
                [InlineKeyboardButton(text=f"{label} (выключен)", callback_data="game:level4")]
            )
        else:
            level_rows.append([InlineKeyboardButton(text=label, callback_data=f"game:level:{level}")])
    return InlineKeyboardMarkup(
        inline_keyboard=level_rows + [
            [InlineKeyboardButton(text="Рулетка без выбора уровня", callback_data="game:roulette")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
            [InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")],
        ],
    )


def intensity_menu(level: int, *, hard_enabled: bool = False) -> InlineKeyboardMarkup:
    hard_button = InlineKeyboardButton(
        text="Жесткие" if hard_enabled else "Жесткие (выключены)",
        callback_data=f"game:intensity:{level}:hard" if hard_enabled else "game:hard",
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Легкие", callback_data=f"game:intensity:{level}:light"),
                InlineKeyboardButton(text="Средние", callback_data=f"game:intensity:{level}:medium"),
                hard_button,
            ],
            [InlineKeyboardButton(text="Рулетка уровня", callback_data=f"game:roulette_level:{level}:any")],
            [InlineKeyboardButton(text="К уровням", callback_data="game:menu")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
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
            [InlineKeyboardButton(text="Рулетка уровня", callback_data=f"game:roulette_level:{level}:{intensity}")],
            [InlineKeyboardButton(text="К уровням", callback_data="game:menu")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
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
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reset_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, завершить", callback_data="game:reset:yes"),
                InlineKeyboardButton(text="Отмена", callback_data="game:reset:no"),
            ],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
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
    rows.append([InlineKeyboardButton(text="В меню", callback_data="game:home")])
    rows.append([InlineKeyboardButton(text="Стоп-слово", callback_data="safe:stopword")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
