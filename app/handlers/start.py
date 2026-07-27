from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import Config
from app.handlers.common import message_thread_id, reject_if_not_allowed
from app.keyboards.game import consent_menu
from app.services.game_service import GameError, GameService

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, config: Config, game_service: GameService) -> None:
    if await reject_if_not_allowed(message, config):
        return
    try:
        game_service.ensure_session(message.chat.id, message_thread_id(message), message.chat.title)
    except GameError as exc:
        await message.answer(str(exc))
        return
    await message.answer(
        "Игра только для взрослых партнеров по взаимному согласию.\n"
        "Стоп-слово доступно в любой момент.",
        reply_markup=consent_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, config: Config) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await message.answer(
        "/start - старт и меню\n"
        "/status - статус бота и сессии\n"
        "/admin - админка контента\n"
        "/reset - завершить сессию с подтверждением\n"
        "/stopword - мгновенно остановить игру"
    )
