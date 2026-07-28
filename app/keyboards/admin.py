from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.labels import (
    BODY_LOAD_NAMES,
    CATEGORY_NAMES,
    INTENSITY_NAMES,
    ITEM_MODE_NAMES,
    LEVEL_NAMES,
    POSE_DIFFICULTY_NAMES,
    POSE_FAMILY_NAMES,
    RISK_TAG_NAMES,
    SPACE_NAMES,
)


def admin_menu(*, restricted_enabled: bool | None = None) -> InlineKeyboardMarkup:
    restricted_text = "Доступ к «Экстриму»"
    if restricted_enabled is not None:
        restricted_text = f"Экстрим: {'доступ открыт' if restricted_enabled else 'доступ закрыт'}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить карточку", callback_data="admin:add")],
            [InlineKeyboardButton(text="Проверка карточек", callback_data="admin:review")],
            [InlineKeyboardButton(text="Карточки на доработке", callback_data="admin:revision_queue:0")],
            [InlineKeyboardButton(text="Каталог карточек", callback_data="admin:catalog")],
            [InlineKeyboardButton(text="Каталог реквизита", callback_data="admin:items:0")],
            [InlineKeyboardButton(text="Сообщения игроков", callback_data="admin:feedback")],
            [InlineKeyboardButton(text="Конфликты обновлений", callback_data="admin:conflicts")],
            [InlineKeyboardButton(text="Импорт XLSX", callback_data="admin:import")],
            [InlineKeyboardButton(text="Экспорт XLSX", callback_data="admin:export")],
            [
                InlineKeyboardButton(
                    text=restricted_text,
                    callback_data="admin:restricted",
                )
            ],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def admin_navigation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="В админку", callback_data="admin:menu")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def category_choice(prefix: str = "admin:cat") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Вопрос", callback_data=f"{prefix}:question"),
                InlineKeyboardButton(text="Задание", callback_data=f"{prefix}:task"),
            ],
            [
                InlineKeyboardButton(text="Поза", callback_data=f"{prefix}:pose"),
                InlineKeyboardButton(text="Желание", callback_data=f"{prefix}:desire"),
            ],
            [InlineKeyboardButton(text="Штраф", callback_data=f"{prefix}:penalty")],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def level_choice(prefix: str = "admin:level", *, include_extreme: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{level} - {name}", callback_data=f"{prefix}:{level}")]
        for level, name in LEVEL_NAMES.items()
    ]
    if include_extreme:
        rows.append([InlineKeyboardButton(text="Экстрим", callback_data=f"{prefix}:extreme")])
    rows.extend(
        [
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def intensity_choice(prefix: str = "admin:intensity") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Легкая", callback_data=f"{prefix}:light"),
                InlineKeyboardButton(text="Средняя", callback_data=f"{prefix}:medium"),
                InlineKeyboardButton(text="Жесткая", callback_data=f"{prefix}:hard"),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def save_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сохранить черновик", callback_data="admin:save:draft")],
            [InlineKeyboardButton(text="На проверку", callback_data="admin:save:needs_review")],
            [InlineKeyboardButton(text="Одобрить и включить", callback_data="admin:save:approved")],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def import_confirm_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Загрузить в базу", callback_data="admin:import:confirm")],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def card_manage(
    card_id: int,
    *,
    archived: bool = False,
    back_callback: str = "admin:catalog",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Редактировать", callback_data=f"admin:editmenu:{card_id}"),
                InlineKeyboardButton(text="Дублировать", callback_data=f"admin:duplicate:{card_id}"),
            ],
            [
                InlineKeyboardButton(text="Одобрить", callback_data=f"admin:approve:{card_id}"),
                InlineKeyboardButton(text="Отключить", callback_data=f"admin:disable:{card_id}"),
            ],
            [
                InlineKeyboardButton(
                    text="Вернуть из архива" if archived else "Архивировать",
                    callback_data=f"admin:archive:{card_id}:{0 if archived else 1}",
                ),
                InlineKeyboardButton(text="Удалить", callback_data=f"admin:deleteask:{card_id}"),
            ],
            [InlineKeyboardButton(text="История версий", callback_data=f"admin:versions:{card_id}")],
            [InlineKeyboardButton(text="Назад к списку", callback_data=back_callback)],
            [InlineKeyboardButton(text="В админку", callback_data="admin:menu")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def card_versions(rows, card_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    f"Версия {row['version_number']} · "
                    f"{row['change_reason'] or 'изменение'} · {row['created_at']}"
                ),
                callback_data=f"admin:version:{card_id}:{row['id']}",
            )
        ]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton(text="К карточке", callback_data=f"admin:card_simple:{card_id}")])
    buttons.append([InlineKeyboardButton(text="В админку", callback_data="admin:menu")])
    buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def card_version_manage(card_id: int, version_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Восстановить эту версию",
                    callback_data=f"admin:restore_version:{card_id}:{version_id}",
                )
            ],
            [InlineKeyboardButton(text="К истории", callback_data=f"admin:versions:{card_id}")],
            [InlineKeyboardButton(text="К карточке", callback_data=f"admin:card_simple:{card_id}")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def seed_conflicts(rows) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{row['external_id']} · {row['content_version']}",
                callback_data=f"admin:conflict:{row['id']}",
            )
        ]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton(text="В админку", callback_data="admin:menu")])
    buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def seed_conflict_choice(conflict_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Оставить мою версию",
                    callback_data=f"admin:resolve_conflict:{conflict_id}:keep",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Применить встроенную",
                    callback_data=f"admin:resolve_conflict:{conflict_id}:apply",
                )
            ],
            [InlineKeyboardButton(text="К конфликтам", callback_data="admin:conflicts")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def card_feedback_list(rows) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{row['external_id'] or '#' + str(row['card_id'])} · {row['created_at']}",
                callback_data=f"admin:feedback_item:{row['id']}",
            )
        ]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton(text="В админку", callback_data="admin:menu")])
    buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def card_feedback_actions(feedback_id: int, card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть карточку", callback_data=f"admin:card_simple:{card_id}")],
            [
                InlineKeyboardButton(
                    text="Отметить обработанным",
                    callback_data=f"admin:feedback_resolve:{feedback_id}",
                )
            ],
            [InlineKeyboardButton(text="К сообщениям", callback_data="admin:feedback")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def review_card_actions(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Все понятно",
                    callback_data=f"admin:review_ok:{card_id}",
                ),
                InlineKeyboardButton(
                    text="На доработку",
                    callback_data=f"admin:review_revision:{card_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Редактировать",
                    callback_data=f"admin:editmenu:{card_id}",
                )
            ],
            [InlineKeyboardButton(text="Завершить просмотр", callback_data="admin:menu")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def review_complete() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Начать проверку заново",
                    callback_data="admin:review_reset",
                )
            ],
            [InlineKeyboardButton(text="В админку", callback_data="admin:menu")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def revision_queue(rows, *, page: int, total: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    f"#{row['id']} · "
                    f"{CATEGORY_NAMES.get(row['category'], row['category'])} · "
                    f"{INTENSITY_NAMES.get(row['intensity'], row['intensity'])}"
                ),
                callback_data=f"admin:revision_card:{row['id']}:{page}",
            )
        ]
        for row in rows
    ]
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="←",
                callback_data=f"admin:revision_queue:{page - 1}",
            )
        )
    if (page + 1) * 10 < total:
        navigation.append(
            InlineKeyboardButton(
                text="→",
                callback_data=f"admin:revision_queue:{page + 1}",
            )
        )
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text="В админку", callback_data="admin:menu")])
    buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def catalog_sections() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{level} - {name}", callback_data=f"admin:catalog_section:{level}")]
        for level, name in LEVEL_NAMES.items()
    ]
    rows.append([InlineKeyboardButton(text="Экстрим", callback_data="admin:catalog_section:x")])
    rows.append([InlineKeyboardButton(text="В админку", callback_data="admin:menu")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_categories(section: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Все карточки", callback_data=f"admin:browse:{section}:all:0")]]
    category_codes = ["question", "task", "pose", "desire", "penalty"]
    for index in range(0, len(category_codes), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=CATEGORY_NAMES[code],
                    callback_data=f"admin:browse:{section}:{code}:0",
                )
                for code in category_codes[index:index + 2]
            ]
        )
    rows.append([InlineKeyboardButton(text="К разделам", callback_data="admin:catalog")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_page(
    rows,
    *,
    section: str,
    category: str,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows:
        status = "архив" if int(row["is_archived"]) else "вкл." if int(row["is_enabled"]) else "выкл."
        label = (
            f"#{row['id']} · {CATEGORY_NAMES.get(row['category'], row['category'])} · "
            f"{INTENSITY_NAMES.get(row['intensity'], row['intensity'])} · {status}"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin:card:{row['id']}:{section}:{category}:{page}",
                )
            ]
        )
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="←",
                callback_data=f"admin:browse:{section}:{category}:{page - 1}",
            )
        )
    if (page + 1) * 10 < total:
        navigation.append(
            InlineKeyboardButton(
                text="→",
                callback_data=f"admin:browse:{section}:{category}:{page + 1}",
            )
        )
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text="К типам карточек", callback_data=f"admin:catalog_section:{section}")])
    buttons.append([InlineKeyboardButton(text="В админку", callback_data="admin:menu")])
    buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def delete_card_confirm(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить карточку", callback_data=f"admin:delete:{card_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:card_simple:{card_id}")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def card_edit_menu(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Текст", callback_data=f"admin:editfield:{card_id}:text"),
                InlineKeyboardButton(text="Название", callback_data=f"admin:editfield:{card_id}:title"),
            ],
            [
                InlineKeyboardButton(text="Уровень", callback_data=f"admin:editchoice:{card_id}:level"),
                InlineKeyboardButton(text="Тип", callback_data=f"admin:editchoice:{card_id}:category"),
            ],
            [
                InlineKeyboardButton(text="Интенсивность", callback_data=f"admin:editchoice:{card_id}:intensity"),
                InlineKeyboardButton(text="Таймер", callback_data=f"admin:editfield:{card_id}:timer_seconds"),
            ],
            [
                InlineKeyboardButton(
                    text="Режим реквизита",
                    callback_data=f"admin:editchoice:{card_id}:item_mode",
                )
            ],
            [InlineKeyboardButton(text="Реквизит", callback_data=f"admin:editfield:{card_id}:required_items")],
            [InlineKeyboardButton(text="К карточке", callback_data=f"admin:card_simple:{card_id}")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def edit_choice(field: str, card_id: int) -> InlineKeyboardMarkup:
    if field == "level":
        rows = [
            [InlineKeyboardButton(text=f"{level} - {name}", callback_data=f"admin:setfield:{card_id}:level:{level}")]
            for level, name in LEVEL_NAMES.items()
        ]
    elif field == "category":
        rows = [
            [InlineKeyboardButton(text=name, callback_data=f"admin:setfield:{card_id}:category:{code}")]
            for code, name in CATEGORY_NAMES.items()
        ]
    elif field == "intensity":
        rows = [
            [
                InlineKeyboardButton(
                    text=name.capitalize(),
                    callback_data=f"admin:setfield:{card_id}:intensity:{code}",
                )
            ]
            for code, name in INTENSITY_NAMES.items()
        ]
    else:
        rows = [
            [
                InlineKeyboardButton(
                    text=name,
                    callback_data=f"admin:setfield:{card_id}:item_mode:{code}",
                )
            ]
            for code, name in ITEM_MODE_NAMES.items()
        ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"admin:editmenu:{card_id}")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_selection(items, selected: set[str], *, prefix: str = "admin:additem") -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        if "is_archived" in item.keys() and int(item["is_archived"]):
            continue
        mark = "✓ " if item["code"] in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{item['name']}",
                    callback_data=f"{prefix}:{item['code']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Готово", callback_data=f"{prefix}:done")])
    rows.append(
        [InlineKeyboardButton(text="Случайный реквизит: можно добавить", callback_data=f"{prefix}:optional")]
    )
    rows.append(
        [InlineKeyboardButton(text="Случайный реквизит: обязателен", callback_data=f"{prefix}:required")]
    )
    rows.append([InlineKeyboardButton(text="Без реквизита", callback_data=f"{prefix}:none")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def timer_choice(prefix: str = "admin:timer") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Без таймера", callback_data=f"{prefix}:0"),
                InlineKeyboardButton(text="30 сек.", callback_data=f"{prefix}:30"),
                InlineKeyboardButton(text="1 мин.", callback_data=f"{prefix}:60"),
            ],
            [
                InlineKeyboardButton(text="90 сек.", callback_data=f"{prefix}:90"),
                InlineKeyboardButton(text="3 мин.", callback_data=f"{prefix}:180"),
                InlineKeyboardButton(text="5 мин.", callback_data=f"{prefix}:300"),
            ],
            [InlineKeyboardButton(text="Другое время", callback_data=f"{prefix}:custom")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def risk_tag_selection(selected: set[str]) -> InlineKeyboardMarkup:
    supported = [
        "power_exchange",
        "roleplay",
        "command_language",
        "denial_play",
        "consent_check",
        "pose_control",
        "sensory_deprivation",
        "food",
        "toys",
        "advanced_practice",
    ]
    rows = []
    for code in supported:
        mark = "✓ " if code in selected else ""
        rows.append(
            [InlineKeyboardButton(text=f"{mark}{RISK_TAG_NAMES[code]}", callback_data=f"admin:risk:{code}")]
        )
    rows.append([InlineKeyboardButton(text="Готово", callback_data="admin:risk:done")])
    rows.append([InlineKeyboardButton(text="Без тем риска", callback_data="admin:risk:none")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_catalog_page(rows, *, page: int, total: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{'архив · ' if int(row['is_archived']) else ''}{row['name']}",
                callback_data=f"admin:item:{row['code']}:{page}",
            )
        ]
        for row in rows
    ]
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="←", callback_data=f"admin:items:{page - 1}"))
    if (page + 1) * 10 < total:
        navigation.append(InlineKeyboardButton(text="→", callback_data=f"admin:items:{page + 1}"))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton(text="Добавить реквизит", callback_data="admin:item_add")])
    buttons.append([InlineKeyboardButton(text="В админку", callback_data="admin:menu")])
    buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def item_manage(code: str, *, archived: bool, page: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Название", callback_data=f"admin:item_edit:{code}:name"),
                InlineKeyboardButton(text="Инструкция", callback_data=f"admin:item_edit:{code}:usage"),
            ],
            [
                InlineKeyboardButton(
                    text="Вернуть из архива" if archived else "Архивировать",
                    callback_data=f"admin:item_archive:{code}:{0 if archived else 1}",
                )
            ],
            [InlineKeyboardButton(text="Удалить", callback_data=f"admin:item_deleteask:{code}")],
            [InlineKeyboardButton(text="К списку", callback_data=f"admin:items:{page}")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def item_delete_confirm(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить реквизит", callback_data=f"admin:item_delete:{code}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:item:{code}:0")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def item_categories_choice(selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for code in ("question", "task", "pose", "desire", "penalty"):
        mark = "✓ " if code in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{CATEGORY_NAMES[code]}",
                    callback_data=f"admin:item_cat:{code}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Готово", callback_data="admin:item_cat:done")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def yes_no_choice(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data=f"{prefix}:1"),
                InlineKeyboardButton(text="Нет", callback_data=f"{prefix}:0"),
            ],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def pose_field_choice(field: str) -> InlineKeyboardMarkup:
    options = {
        "pose_family": POSE_FAMILY_NAMES,
        "pose_difficulty": POSE_DIFFICULTY_NAMES,
        "space_required": SPACE_NAMES,
        "body_load": BODY_LOAD_NAMES,
    }[field]
    rows = [
        [
            InlineKeyboardButton(
                text=label.capitalize(),
                callback_data=f"admin:pose:{field}:{code}",
            )
        ]
        for code, label in options.items()
    ]
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
