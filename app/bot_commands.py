from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from app.config import Config

logger = logging.getLogger(__name__)

PLAYER_COMMANDS = [
    BotCommand(command="start", description="Меню игры"),
    BotCommand(command="stopword", description="Мгновенно остановить игру"),
    BotCommand(command="help", description="Как играть"),
]
ADMIN_COMMANDS = PLAYER_COMMANDS + [
    BotCommand(command="admin", description="Админка карточек"),
    BotCommand(command="status", description="Статус игры"),
]


async def publish_commands(bot: Bot, config: Config) -> None:
    """Fills the «/» menu in Telegram. Failure here must not stop the bot."""
    try:
        await bot.set_my_commands(PLAYER_COMMANDS, scope=BotCommandScopeDefault())
    except Exception:
        logger.warning("could not publish the command menu", exc_info=True)
        return
    for admin_id in sorted(config.admin_user_ids):
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            # The owner has not opened a chat with the bot yet.
            logger.warning("could not publish admin commands for one owner", exc_info=True)
