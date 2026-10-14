from __future__ import annotations

from collections.abc import Mapping

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


LEVEL_ICONS = {1: "💬", 2: "🔥", 3: "❤️‍🔥", 4: "⛓"}
LEVEL_TITLES = {1: "Флирт", 2: "Разогрев", 3: "Секс", 4: "БДСМ"}
LEVEL_HINTS = {
    1: "разговоры, игрушки, фантазии",
    2: "ласки и прелюдия без секса",
    3: "позы, стимуляция, игрушки",
    4: "связывание, шлепки, игра во власть",
}
# Kept for callers that show «N - name».
LEVEL_LABELS = {level: f"{LEVEL_ICONS[level]} {LEVEL_TITLES[level]}" for level in LEVEL_TITLES}

INTENSITY_BUTTONS = {"light": "🌿 Мягко", "medium": "🔥 Средне", "hard": "💥 Жёстко"}
INTENSITY_HINTS = {
    "light": "спокойный темп, без спешки",
    "medium": "смелее и активнее",
    "hard": "на полную",
}

SETTINGS_BUTTON = "⚙️ Настройки"
CATEGORY_LABELS = {
    "question": "💬 Вопрос",
    "task": "🎯 Задание",
    "pose": "🛏 Поза",
    "desire": "🎁 Желание",
}
CATEGORY_HINTS = {
    "question": "поговорить и узнать друг друга",
    "task": "сделать что-то вместе",
    "pose": "попробовать позу",
    "desire": "купон — сохраните и используйте, когда захотите",
}

HOME = "🏠 Меню"
BACK = "⬅️ Назад"


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
        rows.append([_button("▶️ Вернуться к карточке", "game:current")])
    rows.append([_button("🎲 Случайная карточка", "game:roulette")])
    rows.append([_button("🃏 Выбрать уровень", "game:menu")])
    rows.append([_button("🎭 Правда или действие", "tod:menu")])
    if restricted_enabled:
        rows.append([_button("🔞 Экстрим", "game:extreme")])
    desires_text = f"🎁 Желания ({saved_desires})" if saved_desires else "🎁 Желания"
    rows.append([_button(desires_text, "game:desires:0"), _button(SETTINGS_BUTTON, "game:settings")])
    if show_admin:
        rows.append([_button("🛠 Админка", "admin:menu")])
    rows.append([_button("⏹ Закончить игру", "safe:end_game")])
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
    lines = ["🏠 Главное меню"]
    if status.get("active"):
        lines.append(f"Сейчас ходит: {status.get('current_player_label')}")
        used = int(status.get("used_cards") or 0)
        if used:
            lines.append(f"Сыграно карточек: {used}")
        if status.get("has_active_turn"):
            lines.append("▶️ Есть открытая карточка — к ней можно вернуться.")
    lines.append("")
    lines.append("🎲 Случайная — бот сам выберет карточку из уровней в настройках.")
    lines.append("🃏 Выбрать уровень — уровень, интенсивность и тип выбираете вы.")
    lines.append("🎭 Правда или действие — по очереди: вопрос или задание на выбранном уровне.")
    return "\n".join(lines)


def level_menu_text() -> str:
    lines = ["Выберите уровень:", ""]
    for level in LEVEL_TITLES:
        lines.append(f"{LEVEL_ICONS[level]} {LEVEL_TITLES[level]} — {LEVEL_HINTS[level]}")
    return "\n".join(lines)


def intensity_menu_text(level: int) -> str:
    lines = [f"{LEVEL_LABELS[level]}. Насколько интенсивно?", ""]
    for code, label in INTENSITY_BUTTONS.items():
        lines.append(f"{label} — {INTENSITY_HINTS[code]}")
    return "\n".join(lines)


def category_menu_text(level: int, intensity: str, categories: list[str] | None = None) -> str:
    title = LEVEL_LABELS[level]
    if level >= 3:
        title += f" · {INTENSITY_BUTTONS[intensity].split(' ', 1)[1].lower()}"
    lines = [f"{title}. Что выпадет?", ""]
    for code, label in CATEGORY_LABELS.items():
        if categories is None or code in categories:
            lines.append(f"{label} — {CATEGORY_HINTS[code]}")
    return "\n".join(lines)


def settings_menu_text() -> str:
    return (
        "⚙️ Настройки игры\n\n"
        "🎲 Уровни для случайной карточки — из каких уровней берёт карточки «Случайная».\n"
        "🧸 Игрушки и реквизит — отметьте, что у вас есть: карточки с остальным не выпадут.\n"
        "🚧 Границы — что сегодня исключить."
    )


def settings_menu(enabled_levels: tuple[int, ...]) -> InlineKeyboardMarkup:
    levels = ", ".join(LEVEL_TITLES[level] for level in enabled_levels) or "не выбраны"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(f"🎲 Уровни для случайной: {levels}", "game:default_levels")],
            [_button("🧸 Игрушки и реквизит", "inv:menu")],
            [_button("🚧 Границы на сегодня", "boundaries:menu")],
            [_button(HOME, "game:home")],
        ]
    )


def end_game_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("⏹ Да, заканчиваем", "safe:end_game:yes")],
            [_button("▶️ Нет, продолжаем", "game:home")],
        ]
    )


def consent_menu(player_name: str | None = None) -> InlineKeyboardMarkup:
    button_text = f"Подтверждает {player_name}" if player_name else "Подтверждаю"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data="game:base_consent")],
            [InlineKeyboardButton(text=HOME, callback_data="game:home")],
        ]
    )


def level_menu(*, restricted_enabled: bool = False) -> InlineKeyboardMarkup:
    buttons = [_button(LEVEL_LABELS[level], f"game:level:{level}") for level in LEVEL_TITLES]
    rows = [buttons[0:2], buttons[2:4]]
    if restricted_enabled:
        rows.append([_button("🔞 Экстрим", "game:extreme")])
    rows.append([_button("🎲 Случайная из любого уровня", "game:roulette")])
    rows.append([_button(HOME, "game:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def intensity_menu(level: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(label, f"game:intensity:{level}:{code}") for code, label in INTENSITY_BUTTONS.items()],
            [_button("🎲 Случайная на этом уровне", f"game:roulette_level:{level}:any")],
            [_button("⬅️ К уровням", "game:menu"), _button(HOME, "game:home")],
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
            [_button("🎲 Любая из этих", f"game:roulette_level:{level}:{intensity}")],
            [_button("⬅️ К уровням", "game:menu"), _button(HOME, "game:home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_actions(turn_id: int, has_timer: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_timer:
        rows.append([_button("⏱ Запустить таймер", f"game:timer:{turn_id}")])
    rows.extend(
        [
            [_button("✅ Сделали", f"game:done:{turn_id}"), _button("🔄 Другую", f"game:replace:{turn_id}")],
            [_button("🚫 Убрать карточку", f"game:revision:{turn_id}")],
            [_button(HOME, "game:home"), _button("⏹ Закончить", "safe:end_game")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def default_levels_menu(
    selected: tuple[int, ...],
) -> InlineKeyboardMarkup:
    selected_set = set(selected)
    rows = []
    for level, label in LEVEL_LABELS.items():
        mark = "✅" if level in selected_set else "◻️"
        rows.append([_button(f"{mark} {label}", f"game:default_level:{level}")])
    rows.append([_button("💾 Готово", "game:settings")])
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
    ("estim", "Без электростимуляции"),
]


def boundary_menu(selected: set[str] | None = None) -> InlineKeyboardMarkup:
    selected = selected or set()
    rows = []
    for code, label in BOUNDARY_OPTIONS:
        mark = "🚫" if code in selected else "◻️"
        rows.append([_button(f"{mark} {label}", f"boundaries:toggle:{code}")])
    rows.append([_button("💾 Сохранить", "boundaries:save")])
    rows.append([_button(BACK, "game:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# «Правда или действие»: level → intensity (for 3–4) → truth or dare each turn.
TOD_TRUTH = "💬 Правда"
TOD_DARE = "🎯 Действие"


def tod_level_text() -> str:
    lines = [
        "🎭 Правда или действие",
        "",
        "Каждый ход игрок выбирает: «Правда» — честно ответить на вопрос, "
        "«Действие» — выполнить задание. Потом ход переходит ко второму.",
        "",
        "Выберите уровень:",
    ]
    for level in LEVEL_TITLES:
        lines.append(f"{LEVEL_ICONS[level]} {LEVEL_TITLES[level]} — {LEVEL_HINTS[level]}")
    return "\n".join(lines)


def tod_level_menu() -> InlineKeyboardMarkup:
    buttons = [_button(LEVEL_LABELS[level], f"tod:level:{level}") for level in LEVEL_TITLES]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[0:2], buttons[2:4], [_button(HOME, "game:home")]])


def tod_intensity_menu(level: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(label, f"tod:pick:{level}:{code}") for code, label in INTENSITY_BUTTONS.items()],
            [_button("⬅️ К уровням", "tod:menu"), _button(HOME, "game:home")],
        ]
    )


def tod_choice_text(level: int, intensity: str, player_label: str | None = None) -> str:
    title = LEVEL_LABELS[level]
    if level >= 3:
        title += f" · {INTENSITY_BUTTONS[intensity].split(' ', 1)[1].lower()}"
    who = f"Ходит: {player_label}\n\n" if player_label else ""
    return f"🎭 Правда или действие · {title}\n\n{who}Что выбираешь?"


def tod_choice_menu(level: int, intensity: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(TOD_TRUTH, f"tod:draw:{level}:{intensity}:question"),
                _button(TOD_DARE, f"tod:draw:{level}:{intensity}:task"),
            ],
            [_button("🔁 Сменить уровень", "tod:menu"), _button(HOME, "game:home")],
        ]
    )
