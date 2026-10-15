from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.types import ChatMemberUpdated

from app.config import Config
from app.handlers.common import MAX_GROUP_MEMBERS

router = Router(name="membership")
logger = logging.getLogger(__name__)

GROUP_HELLO = (
    "Привет! Играть здесь можно вдвоём с двух телефонов: наберите /start.\n"
    "Кнопки нажимает тот, чья очередь. Если в группе появится кто-то третий, игра здесь остановится."
)


@router.my_chat_member()
async def on_bot_membership(event: ChatMemberUpdated, config: Config) -> None:
    """The bot was added to a group: stay only if one of the partners added it."""
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if event.new_chat_member.status not in ("member", "administrator"):
        return
    added_by = event.from_user.id if event.from_user else None
    if added_by is None or not config.is_allowed(added_by):
        logger.warning("left a group the bot was added to by a stranger")
        await event.bot.leave_chat(event.chat.id)
        return
    text = GROUP_HELLO
    try:
        if await event.bot.get_chat_member_count(event.chat.id) > MAX_GROUP_MEMBERS:
            text = "Здесь больше двух человек — в такой группе я не играю. Создайте группу только на вас двоих."
    except Exception:
        pass
    await event.bot.send_message(event.chat.id, text)
