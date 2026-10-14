from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import Config
from app.handlers.common import message_thread_id, reject_if_not_allowed
from app.handlers.screens import home
from app.keyboards.game import consent_menu
from app.services.game_service import GameError, GameService

router = Router(name="start")

PLAYER_HELP = (
    "Как играть\n"
    "• «Выбрать карточку» — уровень, интенсивность и тип карточки.\n"
    "• «Русская рулетка» — случайная карточка из уровней, выбранных в настройках.\n"
    "• На карточке: «Готово» — передать ход, «Заменить» — другая карточка, "
    "«На доработку» — убрать непонятную карточку из игры.\n"
    "• «Настройки» — уровни рулетки, реквизит и границы на сегодня.\n\n"
    "Команды\n"
    "/start — меню игры\n"
    "/stopword — мгновенно остановить игру\n"
    "/help — эта справка\n\n"
    "Если кнопка не отвечает или устарела, наберите /start."
)
ADMIN_HELP = (
    "\n\nДля владельцев\n"
    "/admin — админка карточек и реквизита\n"
    "/status — технический статус игры"
)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    config: Config,
    game_service: GameService,
    state: FSMContext,
) -> None:
    if await reject_if_not_allowed(message, config):
        return
    if await state.get_state() is not None:
        await state.clear()
        await message.answer("Незаконченное действие в админке отменено.")
    thread_id = message_thread_id(message)
    try:
        game_service.ensure_session(message.chat.id, thread_id, message.chat.title)
    except GameError as exc:
        await message.answer(str(exc))
        return
    if game_service.has_base_consent(message.chat.id, thread_id):
        user_id = message.from_user.id if message.from_user else None
        text, markup = home(game_service, config, message.chat.id, thread_id, user_id)
        await message.answer(text, reply_markup=markup)
        return
    player_name = game_service.next_consent_label(message.chat.id, thread_id)
    await message.answer(
        "Игра только для взрослых партнеров по взаимному согласию.\n"
        "Стоп-слово доступно в любой момент: /stopword.",
        reply_markup=consent_menu(player_name),
    )
    # Reached only when REQUIRE_DAILY_CONSENT=true.


@router.message(Command("help"))
async def cmd_help(message: Message, config: Config) -> None:
    if await reject_if_not_allowed(message, config):
        return
    is_admin = bool(message.from_user and config.is_admin(message.from_user.id))
    await message.answer(PLAYER_HELP + (ADMIN_HELP if is_admin else ""))
