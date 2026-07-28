from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.config import Config


async def answer_callback(callback: CallbackQuery, *args, **kwargs) -> None:
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest as exc:
        message = str(exc).lower()
        if "query is too old" in message or "query id is invalid" in message:
            return
        raise


def message_thread_id(message: Message) -> int | None:
    return getattr(message, "message_thread_id", None)


def callback_thread_id(callback: CallbackQuery) -> int | None:
    if callback.message:
        return getattr(callback.message, "message_thread_id", None)
    return None


async def reject_if_not_allowed(message: Message, config: Config) -> bool:
    user = message.from_user
    if not user or not config.is_allowed(user.id):
        await message.answer("Доступ закрыт")
        return True
    return False


async def reject_callback_if_not_allowed(callback: CallbackQuery, config: Config) -> bool:
    user = callback.from_user
    if not user or not config.is_allowed(user.id):
        await answer_callback(callback, "Доступ закрыт", show_alert=True)
        return True
    return False


async def reject_callback_if_not_admin(callback: CallbackQuery, config: Config) -> bool:
    user = callback.from_user
    if not user or not config.is_admin(user.id):
        await answer_callback(callback, "Админка недоступна", show_alert=True)
        return True
    return False
