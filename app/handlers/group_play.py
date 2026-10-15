"""Playing in a group: the group opens with a password, players join with «Я играю»."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import Config
from app.handlers.common import (
    GROUP_TOO_BIG_TEXT,
    answer_callback,
    group_has_strangers,
    message_thread_id,
    reject_callback_if_not_admin,
)
from app.handlers.screens import home, show_screen
from app.services.game_service import GameError, GameService

router = Router(name="group_play")

PASSWORD_PROMPT = "🔒 Эта группа закрыта. Ответьте на это сообщение паролем, чтобы открыть игру."
NO_PASSWORD_TEXT = "Пароль для групп ещё не задан. Владелец задаёт его в админке бота: «🔑 Пароль для групп»."


class GroupPasswordSetup(StatesGroup):
    password = State()


def _is_group(chat) -> bool:
    return getattr(chat, "type", None) in ("group", "supergroup")


def join_text(game_service: GameService, chat_id: int) -> str:
    need = game_service.players_needed()
    roster = game_service.groups.roster(chat_id)
    names = ", ".join(name for _, name in roster) or "пока никого"
    mode = "Игра на троих" if need == 3 else "Игра вдвоём"
    return (
        f"👥 {mode}. Кто играет?\n\n"
        f"Каждый игрок нажимает «🙋 Я играю». Нужно игроков: {need}.\n"
        f"Уже в игре: {names}."
    )


def join_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🙋 Я играю", callback_data="grp:join")]])


async def start_in_group(message: Message, config: Config, game_service: GameService) -> None:
    """/start in a group: password → «Я играю» → main menu."""
    access = game_service.groups
    chat_id = message.chat.id
    if not access.is_unlocked(chat_id):
        if not access.has_password():
            await message.answer(NO_PASSWORD_TEXT)
            return
        await message.answer(PASSWORD_PROMPT, reply_markup=ForceReply(input_field_placeholder="Пароль"))
        return
    if await group_has_strangers(message.bot, message.chat):
        await message.answer(GROUP_TOO_BIG_TEXT)
        return
    if len(access.roster(chat_id)) < game_service.players_needed():
        await message.answer(join_text(game_service, chat_id), reply_markup=join_menu())
        return
    await _send_home(message, config, game_service)


async def _send_home(message: Message, config: Config, game_service: GameService, prefix: str = "") -> None:
    thread_id = message_thread_id(message)
    try:
        game_service.ensure_session(message.chat.id, thread_id, message.chat.title)
    except GameError as exc:
        await message.answer(str(exc))
        return
    user_id = message.from_user.id if message.from_user else None
    text, markup = home(game_service, config, message.chat.id, thread_id, user_id)
    await message.answer(prefix + text, reply_markup=markup)


@router.message(F.reply_to_message, F.chat.type.in_({"group", "supergroup"}))
async def msg_password(message: Message, config: Config, game_service: GameService) -> None:
    replied = message.reply_to_message
    if not replied or not (replied.text or "").startswith("🔒 Эта группа закрыта"):
        return
    if not replied.from_user or not replied.from_user.is_bot:
        return
    access = game_service.groups
    ok = access.check_password(message.text or "")
    try:
        await message.delete()  # do not leave the password in the chat
    except Exception:
        pass
    if not ok:
        await message.answer("Неверный пароль. Наберите /start, чтобы попробовать ещё раз.")
        return
    access.unlock(message.chat.id, message.from_user.id if message.from_user else None)
    await message.answer("🔓 Группа открыта.\n\n" + join_text(game_service, message.chat.id), reply_markup=join_menu())


@router.callback_query(F.data == "grp:join")
async def cb_join(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    chat = getattr(callback.message, "chat", None)
    if not _is_group(chat) or not game_service.groups.is_unlocked(chat.id):
        await answer_callback(callback, "Сначала откройте группу паролем: /start", show_alert=True)
        return
    if await group_has_strangers(callback.bot, chat):
        await answer_callback(callback, GROUP_TOO_BIG_TEXT, show_alert=True)
        return
    need = game_service.players_needed()
    user = callback.from_user
    name = getattr(user, "first_name", None) or getattr(user, "username", None) or "Игрок"
    if not game_service.groups.join(chat.id, user.id, name, need):
        await answer_callback(callback, "Все места уже заняты.", show_alert=True)
        return
    if len(game_service.groups.roster(chat.id)) < need:
        await show_screen(callback, join_text(game_service, chat.id), join_menu())
        await answer_callback(callback, "Вы в игре!")
        return
    thread_id = getattr(callback.message, "message_thread_id", None)
    try:
        game_service.ensure_session(chat.id, thread_id, getattr(chat, "title", None))
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    text, markup = home(game_service, config, chat.id, thread_id, user.id)
    names = ", ".join(n for _, n in game_service.groups.roster(chat.id))
    await show_screen(callback, f"Все на месте: {names}. Начинаем!\n\n{text}", markup)
    await answer_callback(callback)


# --- admin: the group password ----------------------------------------------

@router.callback_query(F.data == "grp:password")
async def cb_password(callback: CallbackQuery, config: Config, game_service: GameService, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    if _is_group(getattr(callback.message, "chat", None)):
        await answer_callback(callback, "Пароль задаётся только в личке с ботом.", show_alert=True)
        return
    await state.set_state(GroupPasswordSetup.password)
    status = "задан" if game_service.groups.has_password() else "не задан"
    await show_screen(
        callback,
        f"🔑 Пароль для групп ({status})\n\n"
        "Пришлите новый пароль одним сообщением. Я сразу удалю его из чата и сохраню только в зашифрованном виде.\n"
        "Уже открытые группы останутся открытыми.",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin:menu")]]),
    )
    await answer_callback(callback)


@router.message(GroupPasswordSetup.password)
async def msg_new_password(message: Message, config: Config, game_service: GameService, state: FSMContext) -> None:
    if not message.from_user or not config.is_admin(message.from_user.id):
        return
    password = (message.text or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
    if len(password) < 4 or password.startswith("/"):
        await message.answer("Пароль должен быть не короче 4 символов. Пришлите ещё раз.")
        return
    game_service.groups.set_password(password, message.from_user.id)
    await state.clear()
    await message.answer(
        "🔑 Пароль сохранён. В группе наберите /start и ответьте на сообщение бота этим паролем.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В админку", callback_data="admin:menu")]]),
    )
