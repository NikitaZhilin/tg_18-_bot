from __future__ import annotations

from collections.abc import Mapping

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


LEVEL_LABELS = {
    1: "1 - Флирт",
    2: "2 - Разогрев",
    3: "3 - Секс",
    4: "4 - BDSM",
}


SETTINGS_BUTTON = "Настройки"
CATEGORY_LABELS = {
    "question": "Вопрос",
    "task": "Задание",
    "pose": "Поза",
    "desire": "Желание",
}


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu(
    *,
    has_active_turn: bool = False,
    restricted_enabled: bool = False,
    enabled_levels: tuple[int, ...] = (1, 2, 3, 4),
    show_admin: bool = False,
    saved_desires: int = 0,
) -> InlineKeyboardMarkup:
    rows = []
    if has_active_turn:
        rows.append([_button("Продолжить текущую карточку", "game:current")])
    rows.append([_button("Выбрать карточку", "game:menu"), _button("Русская рулетка", "game:roulette")])
    if restricted_enabled:
        rows.append([_button("Экстрим", "game:extreme")])
    desires_text = f"Сохранённые желания ({saved_desires})" if saved_desires else "Сохранённые желания"
    rows.append([_button(desires_text, "game:desires:0")])
    rows.append([_button(SETTINGS_BUTTON, "game:settings")])
    if show_admin:
        rows.append([_button("Админка", "admin:menu")])
    rows.append([_button("Завершить игру", "safe:end_game")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_for_status(status: Mapping[str, object], *, show_admin: bool = False) -> InlineKeyboardMarkup:
    if not status.get("active"):
        return main_menu(show_admin=show_admin)
    return main_menu(
        has_active_turn=bool(status.get("has_active_turn")),
        restricted_enabled=bool(status.get("restricted_content")),
        enabled_levels=tuple(status.get("enabled_levels") or (1, 2, 3, 4)),
        show_admin=show_admin,
        saved_desires=int(status.get("saved_desires") or 0),
    )


def main_menu_text(status: Mapping[str, object]) -> str:
    if not status.get("active"):
        return "Главное меню"
    lines = ["Главное меню", f"Сейчас ходит: {status.get('current_player_label')}."]
    used = int(status.get("used_cards") or 0)
    if used:
        lines.append(f"Карточек в этой игре: {used}.")
    if status.get("has_active_turn"):
        lines.append("Есть незавершённая карточка.")
    return "\n".join(lines)


def settings_menu(enabled_levels: tuple[int, ...]) -> InlineKeyboardMarkup:
    levels = ", ".join(LEVEL_LABELS[level].split(" - ", 1)[-1] for level in enabled_levels) or "не выбраны"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(f"Уровни рулетки: {levels}", "game:default_levels")],
            [_button("Реквизит", "inv:menu")],
            [_button("Границы на сегодня", "boundaries:menu")],
            [_button("В меню", "game:home")],
        ]
    )


def end_game_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Да, завершить игру", "safe:end_game:yes")],
            [_button("Нет, продолжаем", "game:home")],
        ]
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
        ]
    )


def category_menu(level: int, intensity: str, categories: list[str] | None = None) -> InlineKeyboardMarkup:
    available = [code for code in CATEGORY_LABELS if categories is None or code in categories]
    buttons = [
        _button(CATEGORY_LABELS[code], f"game:category:{level}:{intensity}:{code}") for code in available
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.extend(
        [
            [_button("Рулетка уровня", f"game:roulette_level:{level}:{intensity}")],
            [_button("К уровням", "game:menu")],
            [_button("В меню", "game:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_actions(turn_id: int, has_timer: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_timer:
        rows.append([_button("Запустить таймер", f"game:timer:{turn_id}")])
    rows.extend(
        [
            [_button("Готово", f"game:done:{turn_id}"), _button("Заменить", f"game:replace:{turn_id}")],
            [_button("На доработку", f"game:revision:{turn_id}")],
            [_button("В меню", "game:home"), _button("Завершить игру", "safe:end_game")],
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
    rows.append([InlineKeyboardButton(text="Готово", callback_data="game:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reset_confirm() -> InlineKeyboardMarkup:
    # /reset is kept as an alias of «Завершить игру».
    return end_game_confirm()


BOUNDARY_OPTIONS = [
    ("restraint", "Без связывания"),
    ("unbounded_humiliation", "Без унижения"),
    ("impact", "Без шлепков и порки"),
    ("wax", "Без воска"),
    ("sensory_deprivation", "Без сенсорных ограничений"),
    ("food", "Без еды/напитков"),
    ("toys", "Без игрушек"),
    ("neck_play", "Без рук на шее"),
    ("urethral_play", "Без уретральных игр"),
]


def boundary_menu(selected: set[str] | None = None) -> InlineKeyboardMarkup:
    selected = selected or set()
    rows = []
    for code, label in BOUNDARY_OPTIONS:
        mark = "✓ " if code in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"boundaries:toggle:{code}")])
    rows.append([InlineKeyboardButton(text="Сохранить", callback_data="boundaries:save")])
    rows.append([InlineKeyboardButton(text="Назад к настройкам", callback_data="game:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
