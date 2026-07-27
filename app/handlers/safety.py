from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.handlers.common import callback_thread_id, message_thread_id, reject_callback_if_not_allowed, reject_if_not_allowed
from app.keyboards.game import main_menu
from app.services.safety_service import SafetyService

router = Router(name="safety")


STOPWORD_TEXT = "Игра остановлена. Сделайте паузу и обсудите, все ли в порядке."


@router.message(Command("stopword"))
async def cmd_stopword(message: Message, config: Config, safety_service: SafetyService) -> None:
    if await reject_if_not_allowed(message, config):
        return
    user_id = message.from_user.id if message.from_user else None
    safety_service.stopword(message.chat.id, message_thread_id(message), user_id)
    await message.answer(STOPWORD_TEXT, reply_markup=main_menu())


@router.callback_query(F.data == "safe:stopword")
async def cb_stopword(callback: CallbackQuery, config: Config, safety_service: SafetyService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    if not callback.message:
        await callback.answer()
        return
    safety_service.stopword(callback.message.chat.id, callback_thread_id(callback), callback.from_user.id)
    await callback.message.answer(STOPWORD_TEXT, reply_markup=main_menu())
    await callback.answer()
