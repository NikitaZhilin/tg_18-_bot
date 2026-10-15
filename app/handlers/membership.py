from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.types import ChatMemberUpdated

from app.config import Config
from app.handlers.common import max_group_members

router = Router(name="membership")
logger = logging.getLogger(__name__)

GROUP_HELLO = (
    "Привет! Чтобы играть здесь, наберите /start — я попрошу пароль группы.\n"
    "Потом каждый игрок нажимает «🙋 Я играю», и кнопки нажимает тот, чья очередь."
)


@router.my_chat_member()
async def on_bot_membership(event: ChatMemberUpdated, config: Config) -> None:
    """The bot was added to a group: stay only if one of the partners added it."""
    if event.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if event.new_chat_member.status not in ("member", "administrator"):
        return
    # Anyone may add the bot; nothing works there until someone enters the password.
    text = GROUP_HELLO
    try:
        if await event.bot.get_chat_member_count(event.chat.id) > max_group_members():
            text = "Здесь больше двух человек — в такой группе я не играю. Создайте группу только на вас двоих."
    except Exception:
        pass
    await event.bot.send_message(event.chat.id, text)
