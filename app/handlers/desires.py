from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import answer_callback, callback_thread_id, reject_callback_if_not_allowed
from app.keyboards.desires import desire_actions, desire_list
from app.keyboards.game import main_menu
from app.services.desire_service import DesireError, DesireService


router = Router(name="desires")


def _chat_id(callback: CallbackQuery) -> int:
    if not callback.message:
        raise DesireError("Нет сообщения")
    return callback.message.chat.id


@router.callback_query(F.data.startswith("game:desires"))
async def cb_desires(callback: CallbackQuery, config: Config, desire_service: DesireService) -> None:
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
        await callback.message.answer("Сохраненных желаний пока нет.", reply_markup=main_menu())
        await answer_callback(callback)
        return
    await callback.message.answer(
        f"Сохраненные желания: {total}. Страница {page + 1}.",
        reply_markup=desire_list(
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
    await callback.message.answer(
        f"Желание для: {desire_service.player_label(str(desire['owner_slot']))}\n\n"
        f"{desire['title'] or 'Без отдельного названия'}\n\n"
        f"{desire['text']}",
        reply_markup=desire_actions(int(desire_id), int(page)),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:desire_use:"))
async def cb_desire_use(callback: CallbackQuery, config: Config, desire_service: DesireService) -> None:
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
    await callback.message.answer(
        f"Желание использовано:\n\n{desire['text']}",
        reply_markup=main_menu(),
    )
    await answer_callback(callback)
