from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.services import group_access, threesome


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


# Players plus the bot. Anyone else in the group could read the cards.
MAX_GROUP_MEMBERS = 3
GROUP_TOO_BIG_TEXT = (
    "В этой группе есть кто-то кроме игроков — здесь я не играю. "
    "Создайте группу только для тех, кто играет."
)
GROUP_LOCKED_TEXT = "🔒 Группа закрыта. Наберите /start и введите пароль."
NOT_IN_GAME_TEXT = "Вы не участвуете в этой игре. Наберите /start — если есть место, нажмите «🙋 Я играю»."


def _is_group(chat) -> bool:
    return getattr(chat, "type", None) in ("group", "supergroup")


def max_group_members() -> int:
    registry = threesome.registry
    if registry is not None and registry.state().enabled:
        return MAX_GROUP_MEMBERS + 1  # the third player as well
    return MAX_GROUP_MEMBERS


def denial_text(user_id: int, config: Config, chat) -> str | None:
    """None when the user may play here, otherwise what to tell them."""
    groups = group_access.registry
    if groups is not None and _is_group(chat):
        if not groups.is_unlocked(chat.id):
            return GROUP_LOCKED_TEXT
        if not groups.in_roster(chat.id, user_id):
            return NOT_IN_GAME_TEXT
        return None
    return None if config.is_allowed(user_id) else "Доступ закрыт"


def is_player(user_id: int, config: Config, chat) -> bool:
    return denial_text(user_id, config, chat) is None


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
    denial = denial_text(user.id, config, getattr(message, "chat", None)) if user else "Доступ закрыт"
    if denial:
        await message.answer(denial)
        return True
    if await group_has_strangers(getattr(message, "bot", None), getattr(message, "chat", None)):
        await message.answer(GROUP_TOO_BIG_TEXT)
        return True
    return False


async def reject_callback_if_not_allowed(callback: CallbackQuery, config: Config) -> bool:
    user = callback.from_user
    chat = getattr(callback.message, "chat", None)
    denial = denial_text(user.id, config, chat) if user else "Доступ закрыт"
    if denial:
        await answer_callback(callback, denial, show_alert=True)
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
