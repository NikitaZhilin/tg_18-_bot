from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app.handlers.common import (
    answer_callback,
    callback_thread_id,
    message_thread_id,
    reject_callback_if_not_allowed,
    reject_if_not_allowed,
)
from app.handlers.screens import home, show_screen
from app.keyboards.game import end_game_confirm
from app.services.game_service import GameService
from app.services.safety_service import SafetyService

router = Router(name="safety")


STOPWORD_TEXT = "Игра остановлена. Сделайте паузу и обсудите, все ли в порядке."
END_GAME_TEXT = "Игра завершена. Настройки и неиспользованные желания перейдут в следующую игру."
END_GAME_QUESTION = (
    "Завершить игру?\n\n"
    "Незавершённая карточка закроется. Настройки, избранное и неиспользованные желания "
    "сохранятся для следующей игры."
)


@router.message(Command("stopword"))
async def cmd_stopword(
    message: Message,
    config: Config,
    safety_service: SafetyService,
    game_service: GameService,
    state: FSMContext,
) -> None:
    if await reject_if_not_allowed(message, config):
        return
    await state.clear()
    user_id = message.from_user.id if message.from_user else None
    safety_service.stopword(message.chat.id, message_thread_id(message), user_id)
    _, markup = home(game_service, config, message.chat.id, message_thread_id(message), user_id)
    await message.answer(STOPWORD_TEXT, reply_markup=markup)


@router.callback_query(F.data == "safe:stopword")
async def cb_stopword(
    callback: CallbackQuery,
    config: Config,
    safety_service: SafetyService,
    game_service: GameService,
) -> None:
    # Immediate, no confirmation: this is the safety stop.
    if await reject_callback_if_not_allowed(callback, config):
        return
    if not callback.message:
        await answer_callback(callback)
        return
    chat_id, thread_id = callback.message.chat.id, callback_thread_id(callback)
    safety_service.stopword(chat_id, thread_id, callback.from_user.id)
    _, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
    await show_screen(callback, STOPWORD_TEXT, markup)
    await answer_callback(callback)


@router.callback_query(F.data == "safe:end_game")
async def cb_end_game_ask(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    if callback.message is not None:
        await callback.bot.send_message(
            callback.message.chat.id,
            END_GAME_QUESTION,
            reply_markup=end_game_confirm(),
            message_thread_id=callback_thread_id(callback),
        )
    await answer_callback(callback)


@router.callback_query(F.data == "safe:end_game:yes")
async def cb_end_game(
    callback: CallbackQuery,
    config: Config,
    safety_service: SafetyService,
    game_service: GameService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    if not callback.message:
        await answer_callback(callback)
        return
    chat_id, thread_id = callback.message.chat.id, callback_thread_id(callback)
    session = game_service.active_session(chat_id, thread_id)
    safety_service.end_game(chat_id, thread_id, callback.from_user.id)
    summary = game_service.session_summary(int(session["id"])) if session else ""
    _, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
    await show_screen(callback, f"{summary}\n\n{END_GAME_TEXT}" if summary else END_GAME_TEXT, markup)
    await answer_callback(callback)
