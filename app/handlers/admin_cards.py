from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.handlers.common import answer_callback, reject_callback_if_not_admin, reject_if_not_allowed
from app.keyboards.admin import (
    admin_menu,
    admin_navigation,
    card_edit_menu,
    card_manage,
    catalog_categories,
    catalog_page,
    catalog_sections,
    delete_card_confirm,
    edit_choice,
)
from app.labels import CATEGORY_NAMES, INTENSITY_NAMES, ITEM_MODE_NAMES, LEVEL_NAMES, REVIEW_STATUS_NAMES
from app.services.admin_service import AdminService


router = Router(name="admin_cards")


class CardEditState(StatesGroup):
    value = State()


def _section_params(section: str) -> tuple[int | None, bool]:
    return (None, True) if section == "x" else (int(section), False)


def _card_text(card: dict[str, object]) -> str:
    extreme = "restricted_content" in card.get("collections", [])
    section = "Экстрим" if extreme else LEVEL_NAMES[int(card["level"])]
    state = "В архиве" if int(card["is_archived"]) else REVIEW_STATUS_NAMES.get(
        str(card["review_status"]),
        str(card["review_status"]),
    )
    if int(card["is_enabled"]):
        state = "Включена"
    items = ", ".join(str(item["name"]) for item in card.get("required_items", [])) or "не требуется"
    item_mode = ITEM_MODE_NAMES.get(str(card["item_mode"]), str(card["item_mode"]))
    timer = f"{card['timer_seconds']} сек." if card["timer_seconds"] else "нет"
    title = card["title"] or "без отдельного названия"
    return (
        f"{section} · {CATEGORY_NAMES.get(str(card['category']), card['category'])} · "
        f"{INTENSITY_NAMES.get(str(card['intensity']), card['intensity'])}\n"
        f"Карточка #{card['id']} · {state}\n\n"
        f"Название: {title}\n"
        f"Таймер: {timer}\n"
        f"Использование реквизита: {item_mode}\n"
        f"Реквизит: {items}\n\n"
        f"Текст:\n{card['text']}"
    )


async def _show_card(
    callback: CallbackQuery,
    service: AdminService,
    card_id: int,
    *,
    back_callback: str = "admin:catalog",
    answer: bool = True,
) -> None:
    card = service.get_card_detail(card_id)
    if not card or card.get("deleted_at"):
        await answer_callback(callback, "Карточка не найдена.", show_alert=True)
        return
    await callback.message.answer(
        _card_text(card),
        reply_markup=card_manage(
            card_id,
            archived=bool(card["is_archived"]),
            back_callback=back_callback,
        ),
    )
    if answer:
        await answer_callback(callback)


@router.callback_query(F.data == "admin:catalog")
async def cb_catalog(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await callback.message.answer("Выберите раздел:", reply_markup=catalog_sections())
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:catalog_section:"))
async def cb_catalog_section(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    section = callback.data.split(":")[-1]
    name = "Экстрим" if section == "x" else LEVEL_NAMES[int(section)]
    await callback.message.answer(
        f"{name}: выберите тип карточки.",
        reply_markup=catalog_categories(section),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:browse:"))
async def cb_browse(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, section, category, page_raw = callback.data.split(":")
    page = max(0, int(page_raw))
    level, extreme = _section_params(section)
    selected_category = None if category == "all" else category
    rows = admin_service.list_catalog(
        level=level,
        category=selected_category,
        extreme=extreme,
        limit=10,
        offset=page * 10,
    )
    total = admin_service.count_catalog(
        level=level,
        category=selected_category,
        extreme=extreme,
    )
    title = "Экстрим" if extreme else LEVEL_NAMES[int(level)]
    type_name = "все типы" if selected_category is None else CATEGORY_NAMES[selected_category].casefold()
    await callback.message.answer(
        f"{title} · {type_name}\nКарточек: {total}. Страница {page + 1}.",
        reply_markup=catalog_page(
            rows,
            section=section,
            category=category,
            page=page,
            total=total,
        ),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:card:"))
async def cb_card(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, card_id, section, category, page = callback.data.split(":")
    await _show_card(
        callback,
        admin_service,
        int(card_id),
        back_callback=f"admin:browse:{section}:{category}:{page}",
    )


@router.callback_query(F.data.startswith("admin:card_simple:"))
async def cb_card_simple(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await _show_card(callback, admin_service, int(callback.data.split(":")[-1]))


@router.callback_query(F.data.startswith("admin:archive:"))
async def cb_archive_card(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, card_id, archived = callback.data.split(":")
    admin_service.archive_card(callback.from_user.id, int(card_id), bool(int(archived)))
    await answer_callback(callback, "Состояние карточки изменено.")
    await _show_card(callback, admin_service, int(card_id), answer=False)


@router.callback_query(F.data.startswith("admin:deleteask:"))
async def cb_delete_card_ask(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    card_id = int(callback.data.split(":")[-1])
    await callback.message.answer(
        "Удалить карточку? Она исчезнет из каталога и игры, но останется в истории уже сыгранных ходов.",
        reply_markup=delete_card_confirm(card_id),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:delete:"))
async def cb_delete_card(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    card_id = int(callback.data.split(":")[-1])
    admin_service.delete_card(callback.from_user.id, card_id)
    await callback.message.answer("Карточка удалена.", reply_markup=admin_menu())
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:editmenu:"))
async def cb_edit_menu(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    card_id = int(callback.data.split(":")[-1])
    await callback.message.answer(
        f"Что изменить в карточке #{card_id}?",
        reply_markup=card_edit_menu(card_id),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:editchoice:"))
async def cb_edit_choice(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, card_id, field = callback.data.split(":")
    await callback.message.answer("Выберите новое значение:", reply_markup=edit_choice(field, int(card_id)))
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:setfield:"))
async def cb_set_field(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, card_id, field, value = callback.data.split(":")
    admin_service.update_card_field(callback.from_user.id, int(card_id), field, value)
    await callback.message.answer(
        "Изменение сохранено. Карточка переведена в черновик.",
        reply_markup=card_manage(int(card_id)),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:editfield:"))
async def cb_edit_field(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, card_id, field = callback.data.split(":")
    prompts = {
        "text": "Введите новый понятный текст карточки.",
        "title": "Введите новое короткое название или «-», чтобы убрать название.",
        "timer_seconds": "Введите длительность в секундах или «-», чтобы убрать таймер.",
        "required_items": (
            "Введите названия реквизита через запятую. Используйте названия из каталога реквизита. "
            "Отправьте «-», чтобы убрать обязательный реквизит."
        ),
    }
    await state.set_state(CardEditState.value)
    await state.update_data(edit_card_id=int(card_id), edit_field=field)
    await callback.message.answer(prompts[field], reply_markup=admin_navigation())
    await answer_callback(callback)


@router.message(CardEditState.value)
async def msg_edit_value(
    message: Message,
    config: Config,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    if await reject_if_not_allowed(message, config):
        return
    if not message.from_user or not config.is_admin(message.from_user.id):
        await state.clear()
        await message.answer("Админка недоступна.")
        return
    data = await state.get_data()
    card_id = int(data["edit_card_id"])
    field = str(data["edit_field"])
    raw = (message.text or "").strip()
    try:
        if field == "required_items":
            values = [] if raw == "-" else [part.strip() for part in raw.split(",") if part.strip()]
            admin_service.update_card_items(message.from_user.id, card_id, values)
        else:
            value: object = None if raw == "-" else raw
            admin_service.update_card_field(message.from_user.id, card_id, field, value)
    except (ValueError, TypeError) as exc:
        await message.answer(str(exc), reply_markup=admin_navigation())
        return
    await state.clear()
    await message.answer(
        "Изменение сохранено. Карточка переведена в черновик.",
        reply_markup=card_manage(card_id),
    )
