from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.handlers.admin_states import AdminAddCard
from app.handlers.common import answer_callback, message_thread_id, reject_callback_if_not_admin, reject_callback_if_not_allowed, reject_if_not_allowed
from app.keyboards.admin import (
    admin_menu,
    admin_navigation,
    card_manage,
    category_choice,
    intensity_choice,
    item_selection,
    level_choice,
    pose_field_choice,
    risk_tag_selection,
    save_choice,
    timer_choice,
)
from app.keyboards.game import main_menu
from app.labels import CATEGORY_NAMES, INTENSITY_NAMES, LEVEL_NAMES, RISK_TAG_NAMES
from app.services.admin_service import AdminService
from app.services.game_service import GameService

router = Router(name="admin")


def _admin_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    return admin_menu(restricted_enabled=bool(status.get("restricted_content", False)))


def _main_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    if not status["active"]:
        return main_menu()
    return main_menu(
        has_active_turn=bool(status["has_active_turn"]),
        restricted_enabled=bool(status["restricted_content"]),
        enabled_levels=tuple(status["enabled_levels"]),
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, config: Config, game_service: GameService) -> None:
    if await reject_if_not_allowed(message, config):
        return
    if not message.from_user or not config.is_admin(message.from_user.id):
        await message.answer("Админка недоступна.")
        return
    game_service.ensure_session(message.chat.id, message_thread_id(message), message.chat.title)
    await message.answer(
        "Админка контента",
        reply_markup=_admin_menu(game_service, message.chat.id, message_thread_id(message)),
    )


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    game_service: GameService,
) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.clear()
    game_service.ensure_session(
        callback.message.chat.id,
        message_thread_id(callback.message),
        callback.message.chat.title,
    )
    await callback.message.answer(
        "Админка контента",
        reply_markup=_admin_menu(game_service, callback.message.chat.id, message_thread_id(callback.message)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "admin:home")
async def cb_admin_home(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    game_service: GameService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await state.clear()
    await callback.message.answer(
        "Главное меню",
        reply_markup=_main_menu(game_service, callback.message.chat.id, message_thread_id(callback.message)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "admin:add")
async def cb_admin_add(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.clear()
    await state.set_state(AdminAddCard.category)
    await callback.message.answer("Выберите тип карточки:", reply_markup=category_choice())
    await answer_callback(callback)


@router.callback_query(AdminAddCard.category, F.data.startswith("admin:cat:"))
async def cb_admin_category(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.update_data(category=callback.data.split(":")[-1])
    await state.set_state(AdminAddCard.level)
    await callback.message.answer("Выберите раздел:", reply_markup=level_choice(include_extreme=True))
    await answer_callback(callback)


@router.callback_query(AdminAddCard.level, F.data.startswith("admin:level:"))
async def cb_admin_level(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    selected = callback.data.split(":")[-1]
    if selected == "extreme":
        await state.update_data(level=4, intensity="hard", collection="restricted_content")
        await state.set_state(AdminAddCard.title)
        await callback.message.answer(
            "Введите короткое русское название карточки или «-», если отдельное название не нужно.",
            reply_markup=admin_navigation(),
        )
        await answer_callback(callback)
        return
    await state.update_data(level=int(selected), collection=None)
    await state.set_state(AdminAddCard.intensity)
    await callback.message.answer("Выберите интенсивность:", reply_markup=intensity_choice())
    await answer_callback(callback)


@router.callback_query(AdminAddCard.intensity, F.data.startswith("admin:intensity:"))
async def cb_admin_intensity(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.update_data(intensity=callback.data.split(":")[-1])
    await state.set_state(AdminAddCard.title)
    await callback.message.answer(
        "Введите короткое русское название карточки или «-», если отдельное название не нужно.",
        reply_markup=admin_navigation(),
    )
    await answer_callback(callback)


@router.message(AdminAddCard.title)
async def msg_admin_title(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(title="" if message.text == "-" else message.text)
    await state.set_state(AdminAddCard.text)
    await message.answer(
        "Опишите простыми словами, кто и что делает, сколько времени это длится и когда нужно остановиться.",
        reply_markup=admin_navigation(),
    )


@router.message(AdminAddCard.text)
async def msg_admin_text(
    message: Message,
    config: Config,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(text=message.text)
    await state.update_data(required_items=[], item_mode="none")
    await state.set_state(AdminAddCard.required_items)
    await message.answer(
        "Выберите обязательный реквизит или способ случайной подстановки.",
        reply_markup=item_selection(admin_service.export_items(), set()),
    )


@router.callback_query(AdminAddCard.required_items, F.data.startswith("admin:additem:"))
async def cb_admin_items(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    selected = set(data.get("required_items", []))
    if value in {"done", "none", "optional", "required"}:
        if value == "done" and not selected:
            await answer_callback(callback, "Выберите реквизит или другой режим.", show_alert=True)
            return
        await state.update_data(
            required_items=sorted(selected) if value == "done" else [],
            item_mode="required" if value == "done" else value if value in {"optional", "required"} else "none",
        )
        await state.set_state(AdminAddCard.timer)
        await callback.message.answer("Выберите длительность:", reply_markup=timer_choice())
        await answer_callback(callback)
        return
    if value in selected:
        selected.remove(value)
    else:
        selected.add(value)
    await state.update_data(required_items=sorted(selected), item_mode="none")
    await callback.message.edit_reply_markup(
        reply_markup=item_selection(admin_service.export_items(), selected)
    )
    await answer_callback(callback)


@router.message(AdminAddCard.required_items)
async def msg_admin_items(
    message: Message,
    config: Config,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    if await reject_if_not_allowed(message, config):
        return
    lookup = {}
    for item in admin_service.export_items():
        lookup[str(item["code"]).casefold()] = str(item["code"])
        lookup[str(item["name"]).casefold()] = str(item["code"])
    raw_items = [] if message.text == "-" else [
        item.strip() for item in (message.text or "").split(",") if item.strip()
    ]
    unknown = [item for item in raw_items if item.casefold() not in lookup]
    if unknown:
        await message.answer(
            "Не найден реквизит: " + ", ".join(unknown) + ". Используйте кнопки каталога.",
            reply_markup=item_selection(admin_service.export_items(), set()),
        )
        return
    await state.update_data(
        required_items=[lookup[item.casefold()] for item in raw_items],
        item_mode="required",
    )
    await state.set_state(AdminAddCard.timer)
    await message.answer("Введите длительность в секундах или «-» без таймера.", reply_markup=admin_navigation())


@router.callback_query(AdminAddCard.timer, F.data.startswith("admin:timer:"))
async def cb_admin_timer(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    value = callback.data.split(":")[-1]
    if value == "custom":
        await callback.message.answer(
            "Введите целое количество секунд.",
            reply_markup=admin_navigation(),
        )
        await answer_callback(callback)
        return
    await state.update_data(timer_seconds="" if value == "0" else value, risk_tags=[])
    await state.set_state(AdminAddCard.risk_tags)
    await callback.message.answer(
        "Отметьте темы, которые описывают карточку. Это позволит настройкам границ исключать ее.",
        reply_markup=risk_tag_selection(set()),
    )
    await answer_callback(callback)


@router.message(AdminAddCard.timer)
async def msg_admin_timer(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    try:
        timer_seconds = "" if message.text == "-" else str(int(message.text or ""))
    except ValueError:
        await message.answer("Введите целое количество секунд или «-».", reply_markup=admin_navigation())
        return
    await state.update_data(timer_seconds=timer_seconds, risk_tags=[])
    await state.set_state(AdminAddCard.risk_tags)
    await message.answer(
        "Отметьте темы, которые описывают карточку.",
        reply_markup=risk_tag_selection(set()),
    )


@router.callback_query(AdminAddCard.risk_tags, F.data.startswith("admin:risk:"))
async def cb_admin_risk_tags(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    value = callback.data.split(":")[-1]
    data = await state.get_data()
    selected = set(data.get("risk_tags", []))
    if value in {"done", "none"}:
        await state.update_data(risk_tags=[] if value == "none" else sorted(selected))
        data = await state.get_data()
        if data.get("category") == "pose":
            await state.set_state(AdminAddCard.pose_family)
            await callback.message.answer(
                "Выберите семейство позы:",
                reply_markup=pose_field_choice("pose_family"),
            )
        else:
            await _show_preview(callback.message, state)
        await answer_callback(callback)
        return
    if value in selected:
        selected.remove(value)
    else:
        selected.add(value)
    await state.update_data(risk_tags=sorted(selected))
    await callback.message.edit_reply_markup(reply_markup=risk_tag_selection(selected))
    await answer_callback(callback)


@router.message(AdminAddCard.risk_tags)
async def msg_admin_risk_tags(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(
        risk_tags=[] if message.text == "-" else [
            tag.strip() for tag in (message.text or "").split(",") if tag.strip()
        ]
    )
    data = await state.get_data()
    if data.get("category") == "pose":
        await state.set_state(AdminAddCard.pose_family)
        await message.answer("Выберите семейство позы:", reply_markup=pose_field_choice("pose_family"))
        return
    await _show_preview(message, state)


@router.message(AdminAddCard.pose_family)
async def msg_pose_family(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(pose_family=message.text)
    await state.set_state(AdminAddCard.pose_difficulty)
    await message.answer("Выберите сложность позы:", reply_markup=pose_field_choice("pose_difficulty"))


@router.message(AdminAddCard.pose_difficulty)
async def msg_pose_difficulty(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(pose_difficulty=message.text)
    await state.set_state(AdminAddCard.space_required)
    await message.answer("Выберите место:", reply_markup=pose_field_choice("space_required"))


@router.message(AdminAddCard.space_required)
async def msg_space_required(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(space_required=message.text)
    await state.set_state(AdminAddCard.body_load)
    await message.answer("Выберите нагрузку:", reply_markup=pose_field_choice("body_load"))


@router.message(AdminAddCard.body_load)
async def msg_body_load(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(body_load=message.text)
    await _show_preview(message, state)


@router.callback_query(F.data.startswith("admin:pose:"))
async def cb_pose_field(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    _, _, field, value = callback.data.split(":")
    await state.update_data(**{field: value})
    next_field = {
        "pose_family": "pose_difficulty",
        "pose_difficulty": "space_required",
        "space_required": "body_load",
    }.get(field)
    if next_field:
        prompts = {
            "pose_difficulty": "Выберите сложность позы:",
            "space_required": "Выберите место:",
            "body_load": "Выберите нагрузку:",
        }
        await callback.message.answer(prompts[next_field], reply_markup=pose_field_choice(next_field))
    else:
        await _show_preview(callback.message, state)
    await answer_callback(callback)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(AdminAddCard.preview)
    risk_names = ", ".join(RISK_TAG_NAMES.get(tag, tag) for tag in data.get("risk_tags", [])) or "нет"
    section = "Экстрим" if data.get("collection") == "restricted_content" else LEVEL_NAMES[int(data["level"])]
    item_mode_names = {
        "none": "без случайной подстановки",
        "optional": "можно добавить подходящий реквизит",
        "required": "нужно подобрать подходящий реквизит",
    }
    await message.answer(
        "Проверьте карточку перед сохранением:\n\n"
        f"Раздел: {section}\n"
        f"Тип: {CATEGORY_NAMES[data['category']]}\n"
        f"Интенсивность: {INTENSITY_NAMES[data['intensity']]}\n"
        f"Название: {data.get('title') or 'без отдельного названия'}\n"
        f"Реквизит: {item_mode_names.get(data.get('item_mode', 'none'))}\n"
        f"Темы риска: {risk_names}\n\n"
        f"Что нужно сделать:\n{data.get('text')}",
        reply_markup=save_choice(),
    )


@router.callback_query(AdminAddCard.preview, F.data.startswith("admin:save:"))
async def cb_admin_save(callback: CallbackQuery, config: Config, state: FSMContext, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    review_status = callback.data.split(":")[-1]
    data = await state.get_data()
    is_enabled = 1 if review_status == "approved" else 0
    external_id = f"admin_{callback.from_user.id}_{int(callback.message.date.timestamp())}"
    card_data = {
        "external_id": external_id,
        "level": data["level"],
        "category": data["category"],
        "intensity": data["intensity"],
        "title": data.get("title"),
        "text": data["text"],
        "timer_seconds": data.get("timer_seconds"),
        "risk_tags": data.get("risk_tags", []),
        "item_mode": data.get("item_mode", "none"),
        "pose_family": data.get("pose_family"),
        "pose_difficulty": data.get("pose_difficulty"),
        "space_required": data.get("space_required"),
        "body_load": data.get("body_load"),
        "review_status": review_status,
        "is_enabled": is_enabled,
        "aftercare_required": 1 if int(data["level"]) == 4 or data["intensity"] == "hard" else 0,
    }
    card_id = admin_service.create_or_update_card(
        callback.from_user.id,
        card_data,
        required_items=list(data.get("required_items", [])),
        collections=[
            data["collection"]
            if data.get("collection")
            else "kamasutra_inspired_poses"
            if data["category"] == "pose"
            else "base_tasks"
        ],
    )
    await state.clear()
    await callback.message.answer(f"Карточка сохранена: {card_id}", reply_markup=admin_menu())
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:list:"))
async def cb_admin_list(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    status = callback.data.split(":")[-1]
    rows = admin_service.list_by_status(status, limit=8)
    if not rows:
        await callback.message.answer("Список пуст.", reply_markup=admin_menu())
        await answer_callback(callback)
        return
    for row in rows:
        preview = row["text"][:80].replace("\n", " ")
        await callback.message.answer(
            f"#{row['id']} {row['level']}/{row['category']}/{row['intensity']} {row['review_status']}\n{preview}",
            reply_markup=card_manage(int(row["id"])),
        )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:approve:"))
async def cb_admin_approve(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    card_id = int(callback.data.split(":")[-1])
    admin_service.approve_card(callback.from_user.id, card_id)
    await callback.message.answer(f"Карточка #{card_id} одобрена и включена.", reply_markup=admin_menu())
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:disable:"))
async def cb_admin_disable(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    card_id = int(callback.data.split(":")[-1])
    admin_service.disable_card(callback.from_user.id, card_id)
    await callback.message.answer(f"Карточка #{card_id} отключена.", reply_markup=admin_menu())
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:duplicate:"))
async def cb_admin_duplicate(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    card_id = int(callback.data.split(":")[-1])
    external_id = f"copy_{card_id}_{int(callback.message.date.timestamp())}"
    new_id = admin_service.duplicate_card(callback.from_user.id, card_id, external_id)
    await callback.message.answer(f"Создан черновик-копия #{new_id}.", reply_markup=card_manage(new_id))
    await answer_callback(callback)


@router.callback_query(F.data.startswith("admin:edit:"))
async def cb_admin_edit(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    card_id = int(callback.data.split(":")[-1])
    await state.update_data(edit_card_id=card_id)
    await state.set_state(AdminAddCard.edit_text)
    await callback.message.answer(
        f"Введите новый текст для карточки #{card_id}. После правки она станет черновиком.",
        reply_markup=admin_navigation(),
    )
    await answer_callback(callback)


@router.message(AdminAddCard.edit_text)
async def msg_admin_edit_text(message: Message, config: Config, state: FSMContext, admin_service: AdminService) -> None:
    if await reject_if_not_allowed(message, config):
        return
    data = await state.get_data()
    card_id = int(data["edit_card_id"])
    admin_service.update_card_text(message.from_user.id, card_id, message.text or "")
    await state.clear()
    await message.answer(f"Карточка #{card_id} обновлена и переведена в draft.", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:search")
async def cb_admin_search(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.set_state(AdminAddCard.search)
    await callback.message.answer("Введите ID, заголовок или фрагмент текста.", reply_markup=admin_navigation())
    await answer_callback(callback)


@router.message(AdminAddCard.search)
async def msg_admin_search(message: Message, config: Config, state: FSMContext, admin_service: AdminService) -> None:
    if await reject_if_not_allowed(message, config):
        return
    rows = admin_service.search(message.text or "")
    await state.clear()
    if not rows:
        await message.answer("Ничего не найдено.", reply_markup=admin_menu())
        return
    for row in rows[:8]:
        await message.answer(
            f"#{row['id']} {row['level']}/{row['category']}/{row['intensity']} {row['review_status']}\n{row['text'][:80]}",
            reply_markup=card_manage(int(row["id"])),
        )
