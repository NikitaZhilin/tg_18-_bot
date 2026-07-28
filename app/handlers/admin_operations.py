from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.config import Config
from app.handlers.admin_states import AdminAddCard
from app.handlers.common import (
    answer_callback,
    message_thread_id,
    reject_callback_if_not_admin,
    reject_if_not_allowed,
)
from app.keyboards.admin import admin_menu, admin_navigation, import_confirm_choice
from app.services.admin_service import AdminService
from app.services.export_service import save_cards_xlsx
from app.services.game_service import GameError, GameService


router = Router(name="admin_operations")


def _admin_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    return admin_menu(restricted_enabled=bool(status.get("restricted_content", False)))


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
async def msg_admin_import(
    message: Message,
    config: Config,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    if await reject_if_not_allowed(message, config):
        return
    if not message.document:
        await message.answer("Нужно отправить файл.", reply_markup=admin_navigation())
        return
    suffix = Path(message.document.file_name or "").suffix or ".csv"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
    try:
        await message.bot.download(message.document, destination=tmp_path)
        report = admin_service.import_content(message.from_user.id, str(tmp_path), dry_run=True)
    except (OSError, ValueError) as exc:
        tmp_path.unlink(missing_ok=True)
        await state.clear()
        await message.answer(f"Файл не прошел проверку: {exc}", reply_markup=admin_menu())
        return
    await state.update_data(import_path=str(tmp_path))
    await message.answer(
        "Проверка импорта:\n"
        f"строк к загрузке: {report.added_or_updated}\n"
        f"реквизита к загрузке: {report.items_added_or_updated}\n"
        f"disabled: {report.disabled_cards}\n"
        f"needs_review: {report.needs_review}\n"
        f"conflicts: {report.conflicts}\n"
        f"warnings: {report.warnings_count}\n"
        "Если отчет нормальный, можно загрузить файл в базу.",
        reply_markup=import_confirm_choice(),
    )


@router.callback_query(AdminAddCard.import_file, F.data == "admin:import:confirm")
async def cb_admin_import_confirm(
    callback: CallbackQuery,
    config: Config,
    state: FSMContext,
    admin_service: AdminService,
) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    data = await state.get_data()
    import_path = data.get("import_path")
    if not import_path:
        await answer_callback(callback, "Файл не найден", show_alert=True)
        return
    try:
        report = admin_service.import_content(
            callback.from_user.id,
            str(import_path),
            dry_run=False,
        )
    except (OSError, ValueError) as exc:
        await callback.message.answer(f"Импорт не выполнен: {exc}", reply_markup=admin_menu())
        await answer_callback(callback)
        return
    finally:
        Path(str(import_path)).unlink(missing_ok=True)
        await state.clear()
    await callback.message.answer(
        "Импорт выполнен:\n"
        f"загружено: {report.added_or_updated}\n"
        f"реквизита загружено: {report.items_added_or_updated}\n"
        f"disabled: {report.disabled_cards}\n"
        f"needs_review: {report.needs_review}\n"
        f"conflicts: {report.conflicts}\n"
        f"warnings: {report.warnings_count}",
        reply_markup=admin_menu(),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "admin:export")
async def cb_admin_export(
    callback: CallbackQuery,
    config: Config,
    admin_service: AdminService,
) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as handle:
        export_path = handle.name
    try:
        save_cards_xlsx(
            admin_service.export_rows(),
            export_path,
            admin_service.export_items(),
        )
        await callback.message.answer_document(
            FSInputFile(export_path, filename="карточки_и_реквизит.xlsx"),
            caption=(
                "Редактируемая книга карточек и реквизита. "
                "После изменений ее можно загрузить через «Импорт XLSX»."
            ),
            reply_markup=admin_navigation(),
        )
    finally:
        Path(export_path).unlink(missing_ok=True)
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
        await callback.message.answer(
            "Пароль закрытого доступа не настроен на сервере.",
            reply_markup=admin_menu(),
        )
        await answer_callback(callback)
        return
    game_service.ensure_session(
        callback.message.chat.id,
        message_thread_id(callback.message),
        callback.message.chat.title,
    )
    status = game_service.status(callback.message.chat.id, message_thread_id(callback.message))
    if status.get("restricted_content"):
        game_service.disable_restricted_content(
            callback.message.chat.id,
            message_thread_id(callback.message),
        )
        await callback.message.edit_reply_markup(
            reply_markup=_admin_menu(
                game_service,
                callback.message.chat.id,
                message_thread_id(callback.message),
            )
        )
        await answer_callback(callback, "Доступ к разделу «Экстрим» закрыт.")
        return
    await state.set_state(AdminAddCard.restricted_password)
    await callback.message.answer(
        "«Экстрим» — отдельный раздел самых интенсивных карточек. "
        "Он появляется в игровом меню только после ввода админского пароля для текущей сессии.\n\n"
        "Введите админский пароль.",
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
    try:
        await message.delete()
    except Exception:
        pass
    if not config.verify_admin_content_password(message.text or ""):
        await state.clear()
        await message.answer("Пароль неверный.", reply_markup=admin_menu())
        return
    try:
        game_service.ensure_session(
            message.chat.id,
            message_thread_id(message),
            message.chat.title,
        )
        game_service.unlock_restricted_content(message.chat.id, message_thread_id(message))
    except GameError as exc:
        await state.clear()
        await message.answer(str(exc), reply_markup=admin_menu())
        return
    await state.clear()
    await message.answer(
        "Доступ к разделу «Экстрим» открыт для текущей сессии. "
        "Кнопка «Экстрим» уже доступна в главном игровом меню.",
        reply_markup=_admin_menu(game_service, message.chat.id, message_thread_id(message)),
    )


@router.callback_query(F.data == "admin:collections")
async def cb_admin_collections(
    callback: CallbackQuery,
    config: Config,
    admin_service: AdminService,
) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    rows = admin_service.list_collections()
    if not rows:
        await callback.message.answer("Коллекций пока нет.", reply_markup=admin_menu())
        await answer_callback(callback)
        return
    text = "\n".join(
        f"{row['code']} - {row['name']} - карточек: {row['cards_count']} - "
        f"{'on' if row['is_enabled'] else 'off'}"
        for row in rows
    )
    await callback.message.answer(text, reply_markup=admin_menu())
    await answer_callback(callback)


@router.callback_query(F.data == "admin:cancel")
async def cb_admin_cancel(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    data = await state.get_data()
    import_path = data.get("import_path")
    if import_path:
        Path(str(import_path)).unlink(missing_ok=True)
    await state.clear()
    await callback.message.answer("Отменено.", reply_markup=admin_menu())
    await answer_callback(callback)
