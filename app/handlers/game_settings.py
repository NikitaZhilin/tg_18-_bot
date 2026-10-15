from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import answer_callback, callback_thread_id, reject_callback_if_not_allowed
from app.handlers.screens import home, show_screen
from app.keyboards.game import (
    ANAL_CHOICES,
    anal_menu,
    anal_menu_text,
    boundary_menu,
    settings_menu,
    settings_menu_text,
)
from app.keyboards.inventory import inventory_menu
from app.services.game_service import GameError, GameService


router = Router(name="game_settings")


def _chat_id(callback: CallbackQuery) -> int:
    if not callback.message:
        raise GameError("Нет сообщения")
    return callback.message.chat.id


def _settings(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    return settings_menu(tuple(status.get("enabled_levels") or (1, 2, 3, 4)))


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
    await show_screen(
        callback,
        "🧸 Игрушки и реквизит\n\n"
        "Отметьте, что у вас есть. Нажатие переключает: нет → редко → иногда → часто — "
        "так часто бот будет предлагать карточки с этой вещью. "
        "Карточки, где нужна вещь с отметкой «нет», не выпадают.\n\n"
        "Не забудьте нажать «💾 Сохранить».",
        inventory_menu(game_service.available_items(), selected),
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
    await show_screen(
        callback,
        "💾 Игрушки сохранены.\n\n" + settings_menu_text(),
        _settings(game_service, _chat_id(callback), callback_thread_id(callback)),
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
    await show_screen(
        callback,
        "🚧 Границы на сегодня\n\nОтмеченное 🚫 не будет выпадать до конца игры. "
        "Не забудьте нажать «💾 Сохранить».",
        boundary_menu(selected),
    )
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
    await show_screen(
        callback,
        "💾 Границы сохранены.\n\n" + settings_menu_text(),
        _settings(game_service, _chat_id(callback), callback_thread_id(callback)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "anal:menu")
async def cb_anal_menu(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    chat_id, thread_id = _chat_id(callback), callback_thread_id(callback)
    game_service.ensure_session(chat_id, thread_id, callback.message.chat.title if callback.message else None)
    mode = game_service.anal_mode(chat_id, thread_id)
    await show_screen(callback, anal_menu_text(mode), anal_menu(mode))
    await answer_callback(callback)


@router.callback_query(F.data.startswith("anal:set:"))
async def cb_anal_set(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    chat_id, thread_id = _chat_id(callback), callback_thread_id(callback)
    game_service.ensure_session(chat_id, thread_id, callback.message.chat.title if callback.message else None)
    try:
        mode = game_service.set_anal_mode(chat_id, thread_id, callback.data.split(":")[-1], callback.from_user.id)
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    text, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
    await show_screen(callback, f"🍑 Анал: {ANAL_CHOICES[mode]}\n\n{text}", markup)
    await answer_callback(callback)
