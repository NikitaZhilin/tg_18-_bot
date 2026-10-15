from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.services import threesome


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


# Two partners plus the bot. Anyone else in the group could read the cards.
MAX_GROUP_MEMBERS = 3
GROUP_TOO_BIG_TEXT = (
    "В этой группе есть кто-то кроме вас двоих — здесь я не играю. "
    "Создайте группу только на вас двоих."
)


def max_group_members() -> int:
    registry = threesome.registry
    if registry is not None and registry.state().active:
        return MAX_GROUP_MEMBERS + 1  # the third player as well
    return MAX_GROUP_MEMBERS


def is_player(user_id: int, config: Config, chat) -> bool:
    if config.is_allowed(user_id):
        return True
    registry = threesome.registry
    return registry is not None and registry.is_guest(user_id, chat)


async def group_has_strangers(bot, chat) -> bool:
    if chat is None or getattr(chat, "type", None) not in ("group", "supergroup"):
        return False
    try:
        count = await bot.get_chat_member_count(chat.id)
    except Exception:
        return False  # Telegram did not answer: do not block the game over it
    return count > max_group_members()


async def reject_if_not_allowed(message: Message, config: Config) -> bool:
    user = message.from_user
    if not user or not is_player(user.id, config, getattr(message, "chat", None)):
        await message.answer("Доступ закрыт")
        return True
    if await group_has_strangers(getattr(message, "bot", None), getattr(message, "chat", None)):
        await message.answer(GROUP_TOO_BIG_TEXT)
        return True
    return False


async def reject_callback_if_not_allowed(callback: CallbackQuery, config: Config) -> bool:
    user = callback.from_user
    chat = getattr(callback.message, "chat", None)
    if not user or not is_player(user.id, config, chat):
        await answer_callback(callback, "Доступ закрыт", show_alert=True)
        return True
    if await group_has_strangers(getattr(callback, "bot", None), chat):
        await answer_callback(callback, GROUP_TOO_BIG_TEXT, show_alert=True)
        return True
    return False


async def reject_callback_if_not_admin(callback: CallbackQuery, config: Config) -> bool:
    user = callback.from_user
    if not user or not config.is_admin(user.id):
        await answer_callback(callback, "Админка недоступна", show_alert=True)
        return True
    return False
