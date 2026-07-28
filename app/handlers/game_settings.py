from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import answer_callback, callback_thread_id, reject_callback_if_not_allowed
from app.keyboards.game import boundary_menu, main_menu_for_status
from app.keyboards.inventory import inventory_menu
from app.services.game_service import GameError, GameService


router = Router(name="game_settings")


def _chat_id(callback: CallbackQuery) -> int:
    if not callback.message:
        raise GameError("Нет сообщения")
    return callback.message.chat.id


def _main_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    return main_menu_for_status(game_service.status(chat_id, thread_id))


@router.callback_query(F.data == "inv:menu")
async def cb_inventory(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    game_service.ensure_session(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.message.chat.title if callback.message else None,
    )
    selected = game_service.inventory_draft(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.from_user.id,
    )
    await callback.message.answer(
        "Настройте реквизит. Нажатие меняет частоту: выключен → редко → иногда → часто.",
        reply_markup=inventory_menu(game_service.available_items(), selected),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("inv:toggle:"))
async def cb_inventory_toggle(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    selected = game_service.toggle_inventory_draft(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.from_user.id,
        callback.data.split(":")[-1],
    )
    await callback.message.edit_reply_markup(
        reply_markup=inventory_menu(game_service.available_items(), selected)
    )
    await answer_callback(callback)


@router.callback_query(F.data == "inv:save")
async def cb_inventory_save(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    game_service.save_inventory_draft(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.from_user.id,
    )
    await callback.message.answer(
        "Реквизит и частота выпадения сохранены для текущей сессии.",
        reply_markup=_main_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "boundaries:menu")
async def cb_boundaries(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    game_service.ensure_session(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.message.chat.title if callback.message else None,
    )
    selected = game_service.boundaries_draft(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.from_user.id,
    )
    await callback.message.answer("Что сегодня точно исключаем?", reply_markup=boundary_menu(selected))
    await answer_callback(callback)


@router.callback_query(F.data.startswith("boundaries:toggle:"))
async def cb_boundaries_toggle(
    callback: CallbackQuery,
    config: Config,
    game_service: GameService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    selected = game_service.toggle_boundaries_draft(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.from_user.id,
        callback.data.split(":")[-1],
    )
    await callback.message.edit_reply_markup(reply_markup=boundary_menu(selected))
    await answer_callback(callback)


@router.callback_query(F.data == "boundaries:save")
async def cb_boundaries_save(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    game_service.save_boundaries_draft(
        _chat_id(callback),
        callback_thread_id(callback),
        callback.from_user.id,
    )
    await callback.message.answer(
        "Границы сохранены.",
        reply_markup=_main_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
    )
    await answer_callback(callback)
