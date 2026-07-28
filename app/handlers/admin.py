from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.config import Config
from app.handlers.common import answer_callback, message_thread_id, reject_callback_if_not_admin, reject_callback_if_not_allowed, reject_if_not_allowed
from app.keyboards.admin import (
    admin_menu,
    admin_navigation,
    card_manage,
    category_choice,
    import_confirm_choice,
    intensity_choice,
    level_choice,
    save_choice,
)
from app.keyboards.game import main_menu
from app.services.admin_service import AdminService
from app.services.export_service import save_cards_xlsx
from app.services.game_service import GameError, GameService

router = Router(name="admin")


def _admin_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    return admin_menu(restricted_enabled=bool(status.get("restricted_content", False)))


def _main_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    if not status["active"]:
        return main_menu()
    return main_menu(
        allow_level_4=bool(status["allow_level_4"]),
        hard_enabled=status["max_intensity"] == "hard",
        has_active_turn=bool(status["has_active_turn"]),
    )


class AdminAddCard(StatesGroup):
    category = State()
    level = State()
    intensity = State()
    title = State()
    text = State()
    required_items = State()
    timer = State()
    risk_tags = State()
    pose_family = State()
    pose_difficulty = State()
    space_required = State()
    body_load = State()
    preview = State()
    search = State()
    import_file = State()
    edit_text = State()
    restricted_password = State()


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
    await callback.message.answer("Выберите уровень:", reply_markup=level_choice())
    await answer_callback(callback)


@router.callback_query(AdminAddCard.level, F.data.startswith("admin:level:"))
async def cb_admin_level(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.update_data(level=int(callback.data.split(":")[-1]))
    await state.set_state(AdminAddCard.intensity)
    await callback.message.answer("Выберите интенсивность:", reply_markup=intensity_choice())
    await answer_callback(callback)


@router.callback_query(AdminAddCard.intensity, F.data.startswith("admin:intensity:"))
async def cb_admin_intensity(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.update_data(intensity=callback.data.split(":")[-1])
    await state.set_state(AdminAddCard.title)
    await callback.message.answer("Введите название карточки или '-' без названия.", reply_markup=admin_navigation())
    await answer_callback(callback)


@router.message(AdminAddCard.title)
async def msg_admin_title(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(title="" if message.text == "-" else message.text)
    await state.set_state(AdminAddCard.text)
    await message.answer("Введите текст карточки.", reply_markup=admin_navigation())


@router.message(AdminAddCard.text)
async def msg_admin_text(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(text=message.text)
    await state.set_state(AdminAddCard.required_items)
    await message.answer("Введите реквизит кодами через запятую или '-' без реквизита.", reply_markup=admin_navigation())


@router.message(AdminAddCard.required_items)
async def msg_admin_items(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(required_items="" if message.text == "-" else message.text)
    await state.set_state(AdminAddCard.timer)
    await message.answer("Введите таймер в секундах или '-' без таймера.", reply_markup=admin_navigation())


@router.message(AdminAddCard.timer)
async def msg_admin_timer(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(timer_seconds="" if message.text == "-" else message.text)
    await state.set_state(AdminAddCard.risk_tags)
    await message.answer("Введите risk-tags через запятую или '-' без тегов.", reply_markup=admin_navigation())


@router.message(AdminAddCard.risk_tags)
async def msg_admin_risk_tags(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(risk_tags="" if message.text == "-" else message.text)
    data = await state.get_data()
    if data.get("category") == "pose":
        await state.set_state(AdminAddCard.pose_family)
        await message.answer("Для pose: введите pose_family.", reply_markup=admin_navigation())
        return
    await _show_preview(message, state)


@router.message(AdminAddCard.pose_family)
async def msg_pose_family(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(pose_family=message.text)
    await state.set_state(AdminAddCard.pose_difficulty)
    await message.answer("Введите pose_difficulty: easy, medium или hard.", reply_markup=admin_navigation())


@router.message(AdminAddCard.pose_difficulty)
async def msg_pose_difficulty(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(pose_difficulty=message.text)
    await state.set_state(AdminAddCard.space_required)
    await message.answer("Введите space_required: bed, floor, chair, wall или any.", reply_markup=admin_navigation())


@router.message(AdminAddCard.space_required)
async def msg_space_required(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(space_required=message.text)
    await state.set_state(AdminAddCard.body_load)
    await message.answer("Введите body_load: low, medium или high.", reply_markup=admin_navigation())


@router.message(AdminAddCard.body_load)
async def msg_body_load(message: Message, config: Config, state: FSMContext) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.update_data(body_load=message.text)
    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(AdminAddCard.preview)
    await message.answer(
        "Preview:\n"
        f"type: {data.get('category')}\n"
        f"level: {data.get('level')}\n"
        f"intensity: {data.get('intensity')}\n"
        f"title: {data.get('title') or '-'}\n"
        f"text: {data.get('text')}\n"
        f"risk_tags: {data.get('risk_tags') or '-'}",
        reply_markup=save_choice(),
    )


@router.callback_query(AdminAddCard.preview, F.data.startswith("admin:save:"))
async def cb_admin_save(callback: CallbackQuery, config: Config, state: FSMContext, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    review_status = callback.data.split(":")[-1]
    data = await state.get_data()
    is_enabled = 1 if review_status == "approved" else 0
    if int(data["level"]) == 4 or data["intensity"] == "hard":
        is_enabled = 0 if review_status == "approved" else is_enabled
        review_status = "needs_review" if review_status == "approved" else review_status
    external_id = f"admin_{callback.from_user.id}_{int(callback.message.date.timestamp())}"
    card_data = {
        "external_id": external_id,
        "level": data["level"],
        "category": data["category"],
        "intensity": data["intensity"],
        "title": data.get("title"),
        "text": data["text"],
        "timer_seconds": data.get("timer_seconds"),
        "risk_tags": data.get("risk_tags", ""),
        "pose_family": data.get("pose_family"),
        "pose_difficulty": data.get("pose_difficulty"),
        "space_required": data.get("space_required"),
        "body_load": data.get("body_load"),
        "review_status": review_status,
        "is_enabled": is_enabled,
        "requires_both_opt_in": 1 if int(data["level"]) == 4 or data["intensity"] == "hard" else 0,
        "requires_safeword_check": 1 if int(data["level"]) == 4 or data["intensity"] == "hard" else 0,
        "aftercare_required": 1 if int(data["level"]) == 4 or data["intensity"] == "hard" else 0,
    }
    card_id = admin_service.create_or_update_card(
        callback.from_user.id,
        card_data,
        required_items=[item.strip() for item in str(data.get("required_items") or "").split(",") if item.strip()],
        collections=["base_tasks"],
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


@router.callback_query(F.data == "admin:import")
async def cb_admin_import(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.set_state(AdminAddCard.import_file)
    await callback.message.answer(
        "Отправьте CSV/XLSX/DOCX файлом. Сначала будет проверка без загрузки.",
        reply_markup=admin_navigation(),
    )
    await answer_callback(callback)


@router.message(AdminAddCard.import_file)
async def msg_admin_import(message: Message, config: Config, state: FSMContext, admin_service: AdminService) -> None:
    if await reject_if_not_allowed(message, config):
        return
    if not message.document:
        await message.answer("Нужно отправить файл.", reply_markup=admin_navigation())
        return
    suffix = Path(message.document.file_name or "").suffix or ".csv"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
    await message.bot.download(message.document, destination=tmp_path)
    report = admin_service.import_content(message.from_user.id, str(tmp_path), dry_run=True)
    await state.update_data(import_path=str(tmp_path))
    await message.answer(
        "Проверка импорта:\n"
        f"строк к загрузке: {report.added_or_updated}\n"
        f"disabled: {report.disabled_cards}\n"
        f"needs_review: {report.needs_review}\n"
        f"warnings: {report.warnings_count}\n"
        "Если отчет нормальный, можно загрузить файл в базу.",
        reply_markup=import_confirm_choice(),
    )


@router.callback_query(AdminAddCard.import_file, F.data == "admin:import:confirm")
async def cb_admin_import_confirm(callback: CallbackQuery, config: Config, state: FSMContext, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    data = await state.get_data()
    import_path = data.get("import_path")
    if not import_path:
        await answer_callback(callback, "Файл не найден", show_alert=True)
        return
    report = admin_service.import_content(callback.from_user.id, str(import_path), dry_run=False)
    await state.clear()
    await callback.message.answer(
        "Импорт выполнен:\n"
        f"загружено: {report.added_or_updated}\n"
        f"disabled: {report.disabled_cards}\n"
        f"needs_review: {report.needs_review}\n"
        f"warnings: {report.warnings_count}",
        reply_markup=admin_menu(),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "admin:export")
async def cb_admin_export(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    rows = admin_service.export_rows()
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as fh:
        export_path = fh.name
    save_cards_xlsx(rows, export_path)
    await callback.message.answer_document(
        FSInputFile(export_path, filename="cards_export.xlsx"),
        caption="Экспорт карточек (.xlsx)",
        reply_markup=admin_navigation(),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "admin:restricted")
async def cb_admin_restricted(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    game_service: GameService,
) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    if not config.admin_content_password_sha256:
        await callback.message.answer("Пароль закрытого доступа не настроен на сервере.", reply_markup=admin_menu())
        await answer_callback(callback)
        return
    game_service.ensure_session(
        callback.message.chat.id,
        message_thread_id(callback.message),
        callback.message.chat.title,
    )
    status = game_service.status(callback.message.chat.id, message_thread_id(callback.message))
    if status.get("restricted_content"):
        game_service.disable_restricted_content(callback.message.chat.id, message_thread_id(callback.message))
        await callback.message.edit_reply_markup(
            reply_markup=_admin_menu(game_service, callback.message.chat.id, message_thread_id(callback.message))
        )
        await answer_callback(callback, "Закрытые темы выключены.")
        return
    await state.set_state(AdminAddCard.restricted_password)
    await callback.message.answer(
        "Закрытые темы — это отдельные чувствительные карточки. Они не попадают в игру, пока вы не включите их паролем для текущей сессии.\n\nВведите админский пароль.",
        reply_markup=admin_navigation(),
    )
    await answer_callback(callback)


@router.message(AdminAddCard.restricted_password)
async def msg_admin_restricted_password(
    message: Message,
    config: Config,
    state: FSMContext,
    game_service: GameService,
) -> None:
    if await reject_if_not_allowed(message, config):
        return
    if not message.from_user or not config.is_admin(message.from_user.id):
        await state.clear()
        await message.answer("Админка недоступна.")
        return
    password = message.text or ""
    try:
        await message.delete()
    except Exception:
        pass
    if not config.verify_admin_content_password(password):
        await state.clear()
        await message.answer("Пароль неверный.", reply_markup=admin_menu())
        return
    try:
        game_service.ensure_session(message.chat.id, message_thread_id(message), message.chat.title)
        game_service.unlock_restricted_content(message.chat.id, message_thread_id(message))
    except GameError as exc:
        await state.clear()
        await message.answer(str(exc), reply_markup=admin_menu())
        return
    await state.clear()
    await message.answer(
        "Закрытые темы включены для текущей сессии. Их по-прежнему ограничивают выбранный уровень, интенсивность, границы и реквизит.",
        reply_markup=_admin_menu(game_service, message.chat.id, message_thread_id(message)),
    )


@router.callback_query(F.data == "admin:collections")
async def cb_admin_collections(callback: CallbackQuery, config: Config, admin_service: AdminService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    rows = admin_service.list_collections()
    if not rows:
        await callback.message.answer("Коллекций пока нет.", reply_markup=admin_menu())
        await answer_callback(callback)
        return
    text = "\n".join(
        f"{row['code']} - {row['name']} - карточек: {row['cards_count']} - {'on' if row['is_enabled'] else 'off'}"
        for row in rows
    )
    await callback.message.answer(text, reply_markup=admin_menu())
    await answer_callback(callback)


@router.callback_query(F.data == "admin:cancel")
async def cb_admin_cancel(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.clear()
    await callback.message.answer("Отменено.", reply_markup=admin_menu())
    await answer_callback(callback)
