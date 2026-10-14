from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from app.config import Config
from app.keyboards.game import main_menu_for_status, main_menu_text
from app.services.game_service import GameService


def _editable(message: object) -> bool:
    # InaccessibleMessage (older than 48 h or deleted) has no edit methods.
    return message is not None and callable(getattr(message, "edit_text", None))


async def show_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Replace the pressed menu message instead of adding a new one to the chat."""
    message = callback.message
    if _editable(message):
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            # Too old or not editable: fall back to a new message below.
    if message is not None:
        await callback.bot.send_message(
            message.chat.id,
            text,
            reply_markup=reply_markup,
            message_thread_id=getattr(message, "message_thread_id", None),
        )


async def close_card(callback: CallbackQuery, note: str) -> None:
    """Keep a finished card in the chat history, but without its buttons."""
    message = callback.message
    if not _editable(message):
        return
    try:
        await message.edit_text(f"{message.text or ''}\n\n{note}", reply_markup=None)
    except TelegramBadRequest:
        try:
            await message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass


def home(
    game_service: GameService,
    config: Config,
    chat_id: int,
    thread_id: int | None,
    user_id: int | None,
) -> tuple[str, InlineKeyboardMarkup]:
    status = game_service.status(chat_id, thread_id)
    show_admin = bool(user_id and config.is_admin(user_id))
    return main_menu_text(status), main_menu_for_status(status, show_admin=show_admin)
