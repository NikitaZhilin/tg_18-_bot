from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import answer_callback, callback_thread_id, reject_callback_if_not_allowed
from app.services.feedback_service import FeedbackError, FeedbackService


router = Router(name="feedback")


@router.callback_query(F.data.startswith("game:report_unclear:"))
async def cb_report_unclear(
    callback: CallbackQuery,
    config: Config,
    feedback_service: FeedbackService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    if not callback.message:
        await answer_callback(callback, "Сообщение карточки не найдено.", show_alert=True)
        return
    turn_id = int(callback.data.split(":")[-1])
    try:
        created = feedback_service.report_unclear(
            callback.message.chat.id,
            callback_thread_id(callback),
            turn_id,
            callback.from_user.id,
        )
    except FeedbackError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    await answer_callback(
        callback,
        "Карточка добавлена в очередь проверки." if created else "Эта карточка уже отмечена.",
        show_alert=True,
    )
