from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import answer_callback, callback_thread_id, reject_callback_if_not_allowed
from app.keyboards.desires import desire_actions, desire_list
from app.handlers.screens import home, show_screen
from app.services.desire_service import DesireError, DesireService
from app.services.game_service import GameService


router = Router(name="desires")


def _chat_id(callback: CallbackQuery) -> int:
    if not callback.message:
        raise DesireError("Нет сообщения")
    return callback.message.chat.id


def _home(game_service: GameService, config: Config, callback: CallbackQuery):
    return home(game_service, config, _chat_id(callback), callback_thread_id(callback), callback.from_user.id)


@router.callback_query(F.data.startswith("game:desires"))
async def cb_desires(
    callback: CallbackQuery,
    config: Config,
    desire_service: DesireService,
    game_service: GameService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    page = int(callback.data.split(":")[-1]) if callback.data.count(":") == 2 else 0
    try:
        rows = desire_service.list_saved(
            _chat_id(callback),
            callback_thread_id(callback),
            limit=10,
            offset=page * 10,
        )
        total = desire_service.count_saved(_chat_id(callback), callback_thread_id(callback))
    except DesireError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    if not rows:
        text, markup = _home(game_service, config, callback)
        await show_screen(callback, f"Сохранённых желаний пока нет.\n\n{text}", markup)
        await answer_callback(callback)
        return
    await show_screen(
        callback,
        f"Сохранённые желания: {total}. Страница {page + 1}.",
        desire_list(
            rows,
            page=page,
            total=total,
            player_label=desire_service.player_label,
        ),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:desire:"))
async def cb_desire(callback: CallbackQuery, config: Config, desire_service: DesireService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, desire_id, page = callback.data.split(":")
    try:
        desire = desire_service.get_saved(
            _chat_id(callback),
            callback_thread_id(callback),
            int(desire_id),
        )
    except DesireError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    if not desire:
        await answer_callback(callback, "Желание уже использовано или не найдено.", show_alert=True)
        return
    await show_screen(
        callback,
        f"Желание для: {desire_service.player_label(str(desire['owner_slot']))}\n\n"
        f"{desire['title'] or 'Без отдельного названия'}\n\n"
        f"{desire['text']}",
        desire_actions(int(desire_id), int(page)),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:desire_use:"))
async def cb_desire_use(
    callback: CallbackQuery,
    config: Config,
    desire_service: DesireService,
    game_service: GameService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    desire_id = int(callback.data.split(":")[-1])
    try:
        desire = desire_service.use_saved(
            _chat_id(callback),
            callback_thread_id(callback),
            desire_id,
            callback.from_user.id,
        )
    except DesireError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    text, markup = _home(game_service, config, callback)
    await show_screen(callback, f"Желание использовано:\n\n{desire['text']}\n\n{text}", markup)
    await answer_callback(callback)
