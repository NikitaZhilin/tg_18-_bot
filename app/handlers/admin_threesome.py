"""Admin-only switch for the hidden three-player game."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import Config
from app.handlers.common import answer_callback, reject_callback_if_not_admin
from app.handlers.screens import show_screen
from app.services.game_service import GameService

router = Router(name="admin_threesome")


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def threesome_text(state) -> str:
    return "\n".join([
        "👥 Игра на троих — скрытый режим",
        "",
        f"Режим: {'✅ включён' if state.enabled else '⏸ выключен'}",
        "",
        "Работает только в открытой паролем группе. Когда режим включён, в группе ждут троих: "
        "каждый нажимает «🙋 Я играю», и выпадают только карточки для троих. В личке ничего не меняется.",
        "Если переключить режим, игра в группе начнётся заново.",
    ])


def threesome_menu(state) -> InlineKeyboardMarkup:
    toggle = "⏸ Выключить" if state.enabled else "✅ Включить"
    return InlineKeyboardMarkup(inline_keyboard=[[_b(toggle, "three:toggle")], [_b("В админку", "admin:menu")]])


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
