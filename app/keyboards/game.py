from __future__ import annotations

from collections.abc import Mapping

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


LEVEL_LABELS = {
    1: "1 - Флирт",
    2: "2 - Разогрев",
    3: "3 - Секс",
    4: "4 - BDSM",
}


def main_menu(
    *,
    has_active_turn: bool = False,
    restricted_enabled: bool = False,
    enabled_levels: tuple[int, ...] = (1, 2, 3, 4),
) -> InlineKeyboardMarkup:
    rows = []
    if has_active_turn:
        rows.append([InlineKeyboardButton(text="Продолжить текущую карточку", callback_data="game:current")])
    rows.extend(
        [
            [InlineKeyboardButton(text="Выбрать карточку", callback_data="game:menu")],
            [InlineKeyboardButton(text="Русская рулетка", callback_data="game:roulette")],
            [
                InlineKeyboardButton(
                    text="Уровни по умолчанию: "
                    + ", ".join(LEVEL_LABELS[level].split(" - ", 1)[-1] for level in enabled_levels),
                    callback_data="game:default_levels",
                )
            ],
            [InlineKeyboardButton(text="Настроить реквизит", callback_data="inv:menu")],
            [InlineKeyboardButton(text="Границы на сегодня", callback_data="boundaries:menu")],
            [InlineKeyboardButton(text="Сохраненные желания", callback_data="game:desires:0")],
            [InlineKeyboardButton(text="Админка", callback_data="admin:menu")],
            [InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")],
        ]
    )
    if restricted_enabled:
        rows.insert(
            2 if has_active_turn else 1,
            [InlineKeyboardButton(text="Экстрим", callback_data="game:extreme")],
        )
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def main_menu_for_status(status: Mapping[str, object]) -> InlineKeyboardMarkup:
    if not status.get("active"):
        return main_menu()
    return main_menu(
        has_active_turn=bool(status.get("has_active_turn")),
        restricted_enabled=bool(status.get("restricted_content")),
        enabled_levels=tuple(status.get("enabled_levels") or (1, 2, 3, 4)),
    )


def consent_menu(player_name: str | None = None) -> InlineKeyboardMarkup:
    button_text = f"Подтверждает {player_name}" if player_name else "Подтверждаю"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data="game:base_consent")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
        ]
    )


def level_menu(*, restricted_enabled: bool = False) -> InlineKeyboardMarkup:
    level_rows = []
    for level, label in LEVEL_LABELS.items():
        level_rows.append([InlineKeyboardButton(text=label, callback_data=f"game:level:{level}")])
    extra_rows = []
    if restricted_enabled:
        extra_rows.append([InlineKeyboardButton(text="Экстрим", callback_data="game:extreme")])
    return InlineKeyboardMarkup(
        inline_keyboard=level_rows + extra_rows + [
            [InlineKeyboardButton(text="Рулетка без выбора уровня", callback_data="game:roulette")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
            [InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")],
        ],
    )


def intensity_menu(level: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Легкие", callback_data=f"game:intensity:{level}:light"),
                InlineKeyboardButton(text="Средние", callback_data=f"game:intensity:{level}:medium"),
                InlineKeyboardButton(text="Жесткие", callback_data=f"game:intensity:{level}:hard"),
            ],
            [InlineKeyboardButton(text="Рулетка уровня", callback_data=f"game:roulette_level:{level}:any")],
            [InlineKeyboardButton(text="К уровням", callback_data="game:menu")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
            [InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")],
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
            [InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")],
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
                InlineKeyboardButton(text="Заменить карточку", callback_data="game:replace"),
            ],
            [
                InlineKeyboardButton(
                    text="Сообщить о непонятной карточке",
                    callback_data=f"game:report_unclear:{turn_id}",
                )
            ],
            [InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")],
            [InlineKeyboardButton(text="В меню", callback_data="game:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def default_levels_menu(
    selected: tuple[int, ...],
) -> InlineKeyboardMarkup:
    selected_set = set(selected)
    rows = []
    for level, label in LEVEL_LABELS.items():
        mark = "✓ " if level in selected_set else ""
        text = f"{mark}{label}"
        callback_data = f"game:default_level:{level}"
        rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    rows.append([InlineKeyboardButton(text="Готово", callback_data="game:home")])
    rows.append([InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")])
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
    rows.append([InlineKeyboardButton(text="Завершить игру", callback_data="safe:end_game")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
