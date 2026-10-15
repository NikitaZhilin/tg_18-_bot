"""Admin-only switch for the hidden three-player game."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import Config
from app.handlers.common import answer_callback, reject_callback_if_not_admin
from app.handlers.screens import show_screen
from app.services.game_service import GameService

router = Router(name="admin_threesome")


class ThreesomeSetup(StatesGroup):
    third_id = State()
    third_name = State()


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def threesome_text(state) -> str:
    third = f"{state.third_name} (указана)" if state.third_id else "не указана"
    lines = [
        "👥 Игра на троих — скрытый режим",
        "",
        f"Режим: {'✅ включён' if state.enabled else '⏸ выключен'}",
        f"Третья: {third}",
        "",
        "Работает только в группе, где вы трое и бот. В личке ничего не меняется. "
        "Игроки ходят по очереди, выпадают только карточки для троих.",
        "Если переключить режим, игра в группе начнётся заново.",
    ]
    if state.enabled and not state.third_id:
        lines += ["", "⚠️ Режим включён, но третья не указана — пока он не работает."]
    return "\n".join(lines)


def threesome_menu(state) -> InlineKeyboardMarkup:
    toggle = "⏸ Выключить" if state.enabled else "✅ Включить"
    rows = [
        [_b(toggle, "three:toggle")],
        [_b("✏️ Указать третью" if not state.third_id else "✏️ Сменить третью", "three:set")],
    ]
    if state.third_id:
        rows.append([_b("🗑 Убрать третью", "three:clear")])
    rows.append([_b("В админку", "admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show(callback: CallbackQuery, game_service: GameService, prefix: str = "") -> None:
    state = game_service.threesome.state()
    await show_screen(callback, prefix + threesome_text(state), threesome_menu(state))


@router.callback_query(F.data == "three:menu")
async def cb_menu(callback: CallbackQuery, config: Config, game_service: GameService, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.clear()
    await _show(callback, game_service)
    await answer_callback(callback)


@router.callback_query(F.data == "three:toggle")
async def cb_toggle(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    current = game_service.threesome.state()
    game_service.threesome.set_enabled(not current.enabled, callback.from_user.id)
    await _show(callback, game_service)
    await answer_callback(callback)


@router.callback_query(F.data == "three:clear")
async def cb_clear(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    game_service.threesome.clear_third(callback.from_user.id)
    await _show(callback, game_service, "Третья убрана.\n\n")
    await answer_callback(callback)


@router.callback_query(F.data == "three:set")
async def cb_set(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if await reject_callback_if_not_admin(callback, config):
        return
    await state.set_state(ThreesomeSetup.third_id)
    await show_screen(
        callback,
        "Пришлите Telegram ID третьей — только цифры.\n"
        "Свой ID она может узнать у бота @userinfobot.",
        InlineKeyboardMarkup(inline_keyboard=[[_b("Отмена", "three:menu")]]),
    )
    await answer_callback(callback)


@router.message(ThreesomeSetup.third_id)
async def msg_third_id(message: Message, config: Config, state: FSMContext) -> None:
    if not message.from_user or not config.is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Нужны только цифры — ID из @userinfobot. Или нажмите «Отмена».")
        return
    if int(raw) in config.allowed_user_ids:
        await message.answer("Это ID одного из вас двоих. Пришлите ID третьей.")
        return
    await state.update_data(third_id=int(raw))
    await state.set_state(ThreesomeSetup.third_name)
    await message.answer("Как бот будет её называть? Например: Гостья или её имя.")


@router.message(ThreesomeSetup.third_name)
async def msg_third_name(message: Message, config: Config, state: FSMContext, game_service: GameService) -> None:
    if not message.from_user or not config.is_admin(message.from_user.id):
        return
    name = (message.text or "").strip()
    if not name or name.startswith("/"):
        await message.answer("Напишите имя обычным текстом.")
        return
    data = await state.get_data()
    game_service.threesome.set_third(int(data["third_id"]), name, message.from_user.id)
    await state.clear()
    current = game_service.threesome.state()
    await message.answer("Сохранено.\n\n" + threesome_text(current), reply_markup=threesome_menu(current))
