from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu(*, restricted_enabled: bool | None = None) -> InlineKeyboardMarkup:
    restricted_text = "Закрытые темы"
    if restricted_enabled is not None:
        restricted_text = f"Закрытые темы: {'включены' if restricted_enabled else 'выключены'}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить карточку", callback_data="admin:add")],
            [
                InlineKeyboardButton(text="Черновики", callback_data="admin:list:draft"),
                InlineKeyboardButton(text="На проверке", callback_data="admin:list:needs_review"),
            ],
            [
                InlineKeyboardButton(text="Отключенные", callback_data="admin:list:disabled"),
                InlineKeyboardButton(text="Одобренные", callback_data="admin:list:approved"),
            ],
            [InlineKeyboardButton(text="Поиск", callback_data="admin:search")],
            [InlineKeyboardButton(text="Импорт CSV/XLSX", callback_data="admin:import")],
            [InlineKeyboardButton(text="Коллекции", callback_data="admin:collections")],
            [InlineKeyboardButton(text="Экспорт", callback_data="admin:export")],
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
                InlineKeyboardButton(text="question", callback_data=f"{prefix}:question"),
                InlineKeyboardButton(text="task", callback_data=f"{prefix}:task"),
            ],
            [
                InlineKeyboardButton(text="pose", callback_data=f"{prefix}:pose"),
                InlineKeyboardButton(text="desire", callback_data=f"{prefix}:desire"),
            ],
            [InlineKeyboardButton(text="penalty", callback_data=f"{prefix}:penalty")],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def level_choice(prefix: str = "admin:level") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data=f"{prefix}:1"),
                InlineKeyboardButton(text="2", callback_data=f"{prefix}:2"),
                InlineKeyboardButton(text="3", callback_data=f"{prefix}:3"),
                InlineKeyboardButton(text="4", callback_data=f"{prefix}:4"),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )


def intensity_choice(prefix: str = "admin:intensity") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="light", callback_data=f"{prefix}:light"),
                InlineKeyboardButton(text="medium", callback_data=f"{prefix}:medium"),
                InlineKeyboardButton(text="hard", callback_data=f"{prefix}:hard"),
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


def card_manage(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Редактировать текст", callback_data=f"admin:edit:{card_id}"),
                InlineKeyboardButton(text="Дублировать", callback_data=f"admin:duplicate:{card_id}"),
            ],
            [
                InlineKeyboardButton(text="Одобрить", callback_data=f"admin:approve:{card_id}"),
                InlineKeyboardButton(text="Отключить", callback_data=f"admin:disable:{card_id}"),
            ],
            [InlineKeyboardButton(text="В админку", callback_data="admin:menu")],
            [InlineKeyboardButton(text="Главное меню", callback_data="admin:home")],
        ]
    )
