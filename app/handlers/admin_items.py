from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.domain import parse_json_list
from app.handlers.common import answer_callback, reject_callback_if_not_admin, reject_if_not_allowed
from app.keyboards.admin import (
    admin_menu,
    admin_navigation,
    item_catalog_page,
    item_categories_choice,
    item_delete_confirm,
    item_manage,
    level_choice,
    yes_no_choice,
)
from app.labels import CATEGORY_NAMES, LEVEL_NAMES
from app.services.admin_service import AdminService


router = Router(name="admin_items")


class AddItemState(StatesGroup):
    name = State()
    usage = State()


class EditItemState(StatesGroup):
    value = State()


def _item_text(item) -> str:
    categories = ", ".join(
        CATEGORY_NAMES.get(code, code)
        for code in parse_json_list(item["categories"])
    )
    state = "В архиве" if int(item["is_archived"]) else "Активен"
    randomizable = "да" if int(item["randomizable"]) else "нет"
    return (
        f"{item['name']} · {state}\n"
        f"Код: {item['code']}\n"
        f"Уровни: {item['min_level']} ({LEVEL_NAMES[int(item['min_level'])]}) — "
        f"{item['max_level']} ({LEVEL_NAMES[int(item['max_level'])]})\n"
        f"Типы карточек: {categories}\n"
        f"Случайная подстановка: {randomizable}\n\n"
        f"Инструкция для игроков:\n{item['usage_text'] or 'не задана'}"
    )


@router.callback_query(F.data.startswith("admin:items:"))
async def cb_items(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    page = max(0, int(callback.data.split(":")[-1]))
    rows = admin_service.list_items(limit=10, offset=page * 10)
    total = admin_service.count_items()
    await callback.message.answer(
        f"Каталог реквизита\nПунктов: {total}. Страница {page + 1}.",
        reply_markup=item_catalog_page(rows, page=page, total=total),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:item:"))
async def cb_item(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, code, page = callback.data.split(":")
    item = admin_service.get_item(code)
    if not item or item["deleted_at"]:
        await answer_callback(callback, "Реквизит не найден.", show_alert=True)
        return
    await callback.message.answer(
        _item_text(item),
        reply_markup=item_manage(code, archived=bool(item["is_archived"]), page=int(page)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "admin:item_add")
async def cb_item_add(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.clear()
    await state.set_state(AddItemState.name)
    await callback.message.answer(
        "Введите понятное русское название нового реквизита.",
        reply_markup=admin_navigation(),
    )
    await answer_callback(callback)


@router.message(AddItemState.name)
async def msg_item_name(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое.", reply_markup=admin_navigation())
        return
    await state.update_data(item_name=name)
    await message.answer(
        "С какого уровня этот реквизит можно использовать?",
        reply_markup=level_choice("admin:item_min"),
    )


@router.callback_query(F.data.startswith("admin:item_min:"))
async def cb_item_min(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    await state.update_data(item_min_level=level)
    await callback.message.answer(
        "До какого уровня включительно его можно использовать?",
        reply_markup=level_choice("admin:item_max"),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:item_max:"))
async def cb_item_max(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    data = await state.get_data()
    if level < int(data["item_min_level"]):
        await answer_callback(callback, "Максимальный уровень не может быть ниже минимального.", show_alert=True)
        return
    await state.update_data(item_max_level=level, item_categories=[])
    await callback.message.answer(
        "Для каких типов карточек подходит реквизит? Можно выбрать несколько.",
        reply_markup=item_categories_choice(set()),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:item_cat:"))
async def cb_item_category(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    selected = set(data.get("item_categories", []))
    if value == "done":
        if not selected:
            await answer_callback(callback, "Выберите хотя бы один тип карточки.", show_alert=True)
            return
        await state.set_state(AddItemState.usage)
        await callback.message.answer(
            "Введите короткую точную инструкцию: как использовать реквизит в карточке.",
            reply_markup=admin_navigation(),
        )
        await answer_callback(callback)
        return
    if value in selected:
        selected.remove(value)
    else:
        selected.add(value)
    await state.update_data(item_categories=sorted(selected))
    await callback.message.edit_reply_markup(reply_markup=item_categories_choice(selected))
    await answer_callback(callback)


@router.message(AddItemState.usage)
async def msg_item_usage(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    usage = (message.text or "").strip()
    if len(usage) < 10:
        await message.answer("Инструкция слишком короткая.", reply_markup=admin_navigation())
        return
    await state.update_data(item_usage=usage)
    await message.answer(
        "Можно ли боту случайно подставлять этот реквизит в совместимые карточки?",
        reply_markup=yes_no_choice("admin:item_random"),
    )


@router.callback_query(F.data.startswith("admin:item_random:"))
async def cb_item_random(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    data = await state.get_data()
    code = admin_service.create_item(
        callback.from_user.id,
        name=data["item_name"],
        min_level=int(data["item_min_level"]),
        max_level=int(data["item_max_level"]),
        categories=list(data["item_categories"]),
        usage_text=data["item_usage"],
        randomizable=bool(int(callback.data.split(":")[-1])),
    )
    await state.clear()
    item = admin_service.get_item(code)
    await callback.message.answer(
        "Реквизит добавлен.\n\n" + _item_text(item),
        reply_markup=item_manage(code, archived=False),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:item_edit:"))
async def cb_item_edit(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, code, field = callback.data.split(":")
    await state.set_state(EditItemState.value)
    await state.update_data(edit_item_code=code, edit_item_field=field)
    prompt = (
        "Введите новое название реквизита."
        if field == "name"
        else "Введите новую точную инструкцию для игроков."
    )
    await callback.message.answer(prompt, reply_markup=admin_navigation())
    await answer_callback(callback)


@router.message(EditItemState.value)
async def msg_item_edit(
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
    code = str(data["edit_item_code"])
    field = str(data["edit_item_field"])
    value = (message.text or "").strip()
    if len(value) < 2:
        await message.answer("Значение слишком короткое.", reply_markup=admin_navigation())
        return
    kwargs = {"name": value} if field == "name" else {"usage_text": value}
    admin_service.update_item(message.from_user.id, code, **kwargs)
    await state.clear()
    item = admin_service.get_item(code)
    await message.answer(
        "Изменение сохранено.\n\n" + _item_text(item),
        reply_markup=item_manage(code, archived=bool(item["is_archived"])),
    )


@router.callback_query(F.data.startswith("admin:item_archive:"))
async def cb_item_archive(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, code, archived = callback.data.split(":")
    admin_service.archive_item(callback.from_user.id, code, bool(int(archived)))
    item = admin_service.get_item(code)
    await callback.message.answer(
        "Состояние реквизита изменено.\n\n" + _item_text(item),
        reply_markup=item_manage(code, archived=bool(item["is_archived"])),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:item_deleteask:"))
async def cb_item_delete_ask(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    code = callback.data.split(":")[-1]
    await callback.message.answer(
        "Удалить реквизит из каталога? Существующие карточки и история останутся, "
        "но этот пункт больше нельзя будет выбрать в сессии.",
        reply_markup=item_delete_confirm(code),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:item_delete:"))
async def cb_item_delete(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    code = callback.data.split(":")[-1]
    admin_service.delete_item(callback.from_user.id, code)
    await callback.message.answer("Реквизит удален из каталога.", reply_markup=admin_menu())
    await answer_callback(callback)
