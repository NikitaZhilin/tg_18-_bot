from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import callback_thread_id, reject_callback_if_not_allowed
from app.keyboards.game import boundary_menu, card_actions, category_menu, intensity_menu, level_menu, main_menu
from app.keyboards.inventory import ITEMS, inventory_menu
from app.services.card_picker import NoCardsAvailable
from app.services.game_service import GameError, GameService, format_card
from app.services.safety_service import SafetyService
from app.services.timer_service import TimerService

router = Router(name="game")
INVENTORY_SELECTIONS: dict[tuple[int, int], set[str]] = {}
BOUNDARY_SELECTIONS: dict[tuple[int, int], set[str]] = {}


def _chat_id(callback: CallbackQuery) -> int:
    if not callback.message:
        raise GameError("Нет сообщения")
    return callback.message.chat.id


def _inventory_key(callback: CallbackQuery) -> tuple[int, int]:
    return (_chat_id(callback), callback.from_user.id)


@router.callback_query(F.data == "game:menu")
async def cb_game_menu(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    try:
        game_service.ensure_session(_chat_id(callback), callback_thread_id(callback), callback.message.chat.title if callback.message else None)
    except GameError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.message.answer("Выберите уровень:", reply_markup=level_menu())
    await callback.answer()


@router.callback_query(F.data == "game:base_consent")
async def cb_base_consent(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    try:
        game_service.ensure_session(_chat_id(callback), callback_thread_id(callback), callback.message.chat.title if callback.message else None)
        ready = game_service.accept_base_consent(_chat_id(callback), callback_thread_id(callback), callback.from_user.id)
    except GameError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    text = "Оба подтверждения получены. Можно начинать." if ready else "Подтверждение записано. Нужно подтверждение второго игрока."
    await callback.message.answer(text, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("game:level:"))
async def cb_level(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    if level >= 3:
        await callback.message.answer("Выберите интенсивность:", reply_markup=intensity_menu(level))
    else:
        await callback.message.answer("Выберите категорию:", reply_markup=category_menu(level, "light"))
    await callback.answer()


@router.callback_query(F.data.startswith("game:intensity:"))
async def cb_intensity(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity = callback.data.split(":")
    await callback.message.answer("Выберите категорию:", reply_markup=category_menu(int(level), intensity))
    await callback.answer()


@router.callback_query(F.data.startswith("game:category:"))
async def cb_category(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity, category = callback.data.split(":")
    try:
        result = game_service.draw_card(
            _chat_id(callback),
            callback_thread_id(callback),
            callback.from_user.id,
            level=int(level),
            category=category,
            intensity=intensity,
        )
    except NoCardsAvailable:
        await callback.message.answer(
            "Подходящих карточек не осталось или они не подходят под выбранный реквизит.",
            reply_markup=level_menu(),
        )
        await callback.answer()
        return
    except GameError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.message.answer(
        format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await callback.answer()


@router.callback_query(F.data == "game:roulette")
async def cb_roulette(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    try:
        result = game_service.draw_card(
            _chat_id(callback),
            callback_thread_id(callback),
            callback.from_user.id,
            level=None,
            category=None,
            intensity=None,
            source="roulette",
        )
    except NoCardsAvailable:
        await callback.message.answer(
            "Подходящих карточек не осталось или они не подходят под выбранный реквизит.",
            reply_markup=level_menu(),
        )
        await callback.answer()
        return
    except GameError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.message.answer(
        format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await callback.answer()


@router.callback_query(F.data == "game:done")
async def cb_done(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    game_service.finish_turn(_chat_id(callback), callback_thread_id(callback), callback.from_user.id, "completed")
    await callback.message.answer("Ход завершен. Передаю ход партнеру.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "game:skip")
async def cb_skip(callback: CallbackQuery, config: Config, game_service: GameService, safety_service: SafetyService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    session = game_service.active_session(_chat_id(callback), callback_thread_id(callback))
    if session:
        safety_service.safe_skip(int(session["id"]), session["active_turn_id"], callback.from_user.id)
    game_service.finish_turn(_chat_id(callback), callback_thread_id(callback), callback.from_user.id, "skipped")
    await callback.message.answer("Карточка пропущена без штрафа. Передаю ход партнеру.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("game:timer:"))
async def cb_timer(callback: CallbackQuery, config: Config, timer_service: TimerService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    turn_id = int(callback.data.split(":")[-1])
    try:
        timer_id = timer_service.start_for_turn(turn_id, callback.from_user.id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.message.answer(f"Таймер запущен. ID: {timer_id}")
    await callback.answer()


@router.callback_query(F.data == "game:reset:yes")
async def cb_reset_yes(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    game_service.reset_session(_chat_id(callback), callback_thread_id(callback))
    await callback.message.answer("Сессия завершена.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "game:reset:no")
async def cb_reset_no(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await callback.message.answer("Продолжаем.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "game:level4")
async def cb_level4(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    enabled = game_service.set_level_4_consent(_chat_id(callback), callback_thread_id(callback), callback.from_user.id, True)
    text = "Уровень 4 включен." if enabled else "Согласие записано. Нужно подтверждение второго игрока."
    await callback.message.answer(text, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "game:hard")
async def cb_hard(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    enabled = game_service.set_hard_consent(_chat_id(callback), callback_thread_id(callback), callback.from_user.id, True)
    text = "Hard-интенсивность включена." if enabled else "Согласие записано. Нужно подтверждение второго игрока."
    await callback.message.answer(text, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "inv:menu")
async def cb_inventory(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    selected = set()
    INVENTORY_SELECTIONS[_inventory_key(callback)] = selected
    await callback.message.answer("Что сегодня используем?", reply_markup=inventory_menu(selected))
    await callback.answer()


@router.callback_query(F.data.startswith("inv:toggle:"))
async def cb_inventory_toggle(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    code = callback.data.split(":")[-1]
    key = _inventory_key(callback)
    selected = INVENTORY_SELECTIONS.setdefault(key, set())
    if code in selected:
        selected.remove(code)
    else:
        selected.add(code)
    await callback.message.edit_reply_markup(reply_markup=inventory_menu(selected))
    await callback.answer()


@router.callback_query(F.data == "inv:save")
async def cb_inventory_save(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    selected = INVENTORY_SELECTIONS.pop(_inventory_key(callback), set())
    game_service.set_items_for_active_session(_chat_id(callback), callback_thread_id(callback), sorted(selected))
    await callback.message.answer("Реквизит сохранен.", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "boundaries:menu")
async def cb_boundaries(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    selected = game_service.boundaries_for_active_session(_chat_id(callback), callback_thread_id(callback))
    BOUNDARY_SELECTIONS[_inventory_key(callback)] = set(selected)
    await callback.message.answer("Что сегодня точно исключаем?", reply_markup=boundary_menu(selected))
    await callback.answer()


@router.callback_query(F.data.startswith("boundaries:toggle:"))
async def cb_boundaries_toggle(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    code = callback.data.split(":")[-1]
    key = _inventory_key(callback)
    selected = BOUNDARY_SELECTIONS.setdefault(key, set())
    if code in selected:
        selected.remove(code)
    else:
        selected.add(code)
    await callback.message.edit_reply_markup(reply_markup=boundary_menu(selected))
    await callback.answer()


@router.callback_query(F.data == "boundaries:save")
async def cb_boundaries_save(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    selected = BOUNDARY_SELECTIONS.pop(_inventory_key(callback), set())
    game_service.set_boundaries_for_active_session(
        _chat_id(callback),
        callback_thread_id(callback),
        sorted(selected),
        callback.from_user.id,
    )
    await callback.message.answer("Границы сохранены.", reply_markup=main_menu())
    await callback.answer()
