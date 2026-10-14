from __future__ import annotations

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.handlers.common import answer_callback

router = Router(name="fallback")

STALE_BUTTON_TEXT = "Эта кнопка устарела. Откройте меню командой /start."
UNKNOWN_MESSAGE_TEXT = "Не понял сообщение. Пользуйтесь кнопками меню или наберите /start."


@router.callback_query()
async def cb_stale_button(callback: CallbackQuery) -> None:
    # Registered last: answers buttons from old menus instead of an endless spinner.
    await answer_callback(callback, STALE_BUTTON_TEXT, show_alert=True)


@router.message()
async def msg_unknown(message: Message, config: Config) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return
    if not message.from_user or not config.is_allowed(message.from_user.id):
        return
    await message.answer(UNKNOWN_MESSAGE_TEXT)
