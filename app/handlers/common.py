from __future__ import annotations

from aiogram.types import CallbackQuery, Message

from app.config import Config


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
        await callback.answer("Доступ закрыт", show_alert=True)
        return True
    return False


async def reject_callback_if_not_admin(callback: CallbackQuery, config: Config) -> bool:
    user = callback.from_user
    if not user or not config.is_admin(user.id):
        await callback.answer("Админка недоступна", show_alert=True)
        return True
    return False
