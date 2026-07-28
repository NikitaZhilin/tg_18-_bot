from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Config
from app.handlers.common import message_thread_id, reject_if_not_allowed
from app.keyboards.game import reset_confirm
from app.services.game_service import GameService

router = Router(name="status")


@router.message(Command("status"))
async def cmd_status(message: Message, config: Config, game_service: GameService) -> None:
    if await reject_if_not_allowed(message, config):
        return
    if not message.from_user or not config.is_admin(message.from_user.id):
        await message.answer("Команда доступна только владельцам.")
        return
    status = game_service.status(message.chat.id, message_thread_id(message))
    if not status["active"]:
        await message.answer("Активной сессии нет.")
        return
    await message.answer(
        "Статус:\n"
        f"session_id: {status['session_id']}\n"
        f"текущий игрок: {status['current_player_label']} ({status['current_player_id']})\n"
        f"использовано карточек: {status['used_cards']}\n"
        f"активный таймер: {status['active_timer'] or 'нет'}\n"
        f"Экстрим: {'доступ открыт' if status['restricted_content'] else 'доступ закрыт'}\n"
        f"dry_run: {config.dry_run}"
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, config: Config) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await message.answer("Завершить текущую сессию?", reply_markup=reset_confirm())
