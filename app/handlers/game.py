from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import answer_callback, callback_thread_id, reject_callback_if_not_allowed
from app.keyboards.game import (
    card_actions,
    category_menu,
    consent_menu,
    default_levels_menu,
    intensity_menu,
    level_menu,
    main_menu_for_status,
)
from app.services.card_picker import NoCardsAvailable
from app.services.game_service import BASE_CONSENT_REQUIRED, GameError, GameService, format_card
from app.services.safety_service import SafetyService
from app.services.timer_service import TimerService

router = Router(name="game")


def _chat_id(callback: CallbackQuery) -> int:
    if not callback.message:
        raise GameError("Нет сообщения")
    return callback.message.chat.id


def _main_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    return main_menu_for_status(game_service.status(chat_id, thread_id))


def _level_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    return level_menu(
        restricted_enabled=bool(status.get("restricted_content", False)),
    )


async def _show_game_error(callback: CallbackQuery, exc: GameError) -> None:
    if str(exc) == BASE_CONSENT_REQUIRED:
        await callback.message.answer(
            "Перед первой карточкой подтвердите согласие на игру.",
            reply_markup=consent_menu(),
        )
        await answer_callback(callback)
        return
    await answer_callback(callback, str(exc), show_alert=True)


@router.callback_query(F.data == "game:home")
async def cb_game_home(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await callback.message.answer(
        "Главное меню",
        reply_markup=_main_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:current")
async def cb_current_card(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    result = game_service.current_card(_chat_id(callback), callback_thread_id(callback))
    if not result:
        await answer_callback(callback, "Незавершенной карточки нет.", show_alert=True)
        return
    await callback.message.answer(
        format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:menu")
async def cb_game_menu(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    try:
        game_service.ensure_session(_chat_id(callback), callback_thread_id(callback), callback.message.chat.title if callback.message else None)
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    if not game_service.has_base_consent(_chat_id(callback), callback_thread_id(callback)):
        player_name = game_service.next_consent_label(
            _chat_id(callback),
            callback_thread_id(callback),
        )
        await callback.message.answer(
            f"Перед первой карточкой согласие подтверждает {player_name}.",
            reply_markup=consent_menu(player_name),
        )
        await answer_callback(callback)
        return
    await callback.message.answer(
        "Выберите уровень:",
        reply_markup=_level_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:base_consent")
async def cb_base_consent(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    try:
        game_service.ensure_session(_chat_id(callback), callback_thread_id(callback), callback.message.chat.title if callback.message else None)
        ready = game_service.accept_base_consent(_chat_id(callback), callback_thread_id(callback), callback.from_user.id)
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    next_player = (
        None
        if ready
        else game_service.next_consent_label(_chat_id(callback), callback_thread_id(callback))
    )
    text = (
        "Оба подтверждения получены. Можно начинать."
        if ready
        else f"Подтверждение записано. Теперь подтверждает {next_player}."
    )
    await callback.message.answer(
        text,
        reply_markup=(
            _main_menu(game_service, _chat_id(callback), callback_thread_id(callback))
            if ready
            else consent_menu(next_player)
        ),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:level:"))
async def cb_level(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    if level >= 3:
        await callback.message.answer(
            "Выберите интенсивность:",
            reply_markup=intensity_menu(level),
        )
    else:
        await callback.message.answer("Выберите категорию:", reply_markup=category_menu(level, "light"))
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:intensity:"))
async def cb_intensity(callback: CallbackQuery, config: Config) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity = callback.data.split(":")
    await callback.message.answer("Выберите категорию:", reply_markup=category_menu(int(level), intensity))
    await answer_callback(callback)


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
            reply_markup=_level_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
        )
        await answer_callback(callback)
        return
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    await callback.message.answer(
        format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await answer_callback(callback)


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
            reply_markup=_level_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
        )
        await answer_callback(callback)
        return
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    await callback.message.answer(
        format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:extreme")
async def cb_extreme(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
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
            collection_code="restricted_content",
        )
    except NoCardsAvailable:
        await answer_callback(callback, "В разделе «Экстрим» не осталось подходящих карточек.", show_alert=True)
        return
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    await callback.message.answer(
        format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:roulette_level:"))
async def cb_roulette_level(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity = callback.data.split(":")
    selected_intensity = None if intensity == "any" else intensity
    try:
        result = game_service.draw_card(
            _chat_id(callback),
            callback_thread_id(callback),
            callback.from_user.id,
            level=int(level),
            category=None,
            intensity=selected_intensity,
            source="roulette",
        )
    except NoCardsAvailable:
        await callback.message.answer(
            "Подходящих карточек не осталось или они не подходят под выбранный реквизит.",
            reply_markup=_level_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
        )
        await answer_callback(callback)
        return
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    await callback.message.answer(
        format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:done")
async def cb_done(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    try:
        next_player = game_service.finish_turn(
            _chat_id(callback),
            callback_thread_id(callback),
            callback.from_user.id,
            "completed",
        )
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    await callback.message.answer(
        f"Ход завершен. Следующий: {next_player}.",
        reply_markup=_main_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:replace")
@router.callback_query(F.data == "game:skip")
async def cb_replace_card(
    callback: CallbackQuery,
    config: Config,
    game_service: GameService,
    safety_service: SafetyService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    session = game_service.active_session(_chat_id(callback), callback_thread_id(callback))
    session_id = int(session["id"]) if session else None
    turn_id = int(session["active_turn_id"]) if session and session["active_turn_id"] else None
    try:
        result = game_service.replace_active_card(
            _chat_id(callback),
            callback_thread_id(callback),
            callback.from_user.id,
        )
    except NoCardsAvailable:
        current = game_service.current_card(
            _chat_id(callback),
            callback_thread_id(callback),
        )
        await callback.message.answer(
            "Другой подходящей карточки по этим условиям нет. Текущая карточка сохранена.",
            reply_markup=(
                card_actions(current.turn_id, bool(current.card.timer_seconds))
                if current
                else _main_menu(game_service, _chat_id(callback), callback_thread_id(callback))
            ),
        )
        await answer_callback(callback)
        return
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    if session_id:
        safety_service.safe_skip(session_id, turn_id, callback.from_user.id)
    await callback.message.answer(
        "Новая карточка:\n\n" + format_card(result.card),
        reply_markup=card_actions(result.turn_id, bool(result.card.timer_seconds)),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:revision:"))
async def cb_request_card_revision(
    callback: CallbackQuery,
    config: Config,
    game_service: GameService,
    safety_service: SafetyService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    turn_id = int(callback.data.split(":")[-1])
    session = game_service.active_session(_chat_id(callback), callback_thread_id(callback))
    session_id = int(session["id"]) if session else None
    try:
        replacement = game_service.request_card_revision(
            _chat_id(callback),
            callback_thread_id(callback),
            callback.from_user.id,
            turn_id,
        )
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    if session_id:
        safety_service.safe_skip(session_id, turn_id, callback.from_user.id)
    if replacement is None:
        await callback.message.answer(
            "Карточка отправлена на доработку и больше не будет выпадать. "
            "Другой карточки с теми же условиями сейчас нет.",
            reply_markup=_main_menu(
                game_service,
                _chat_id(callback),
                callback_thread_id(callback),
            ),
        )
        await answer_callback(callback)
        return
    await callback.message.answer(
        "Карточка отправлена на доработку.\n\nНовая карточка:\n\n"
        + format_card(replacement.card),
        reply_markup=card_actions(
            replacement.turn_id,
            bool(replacement.card.timer_seconds),
        ),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:default_levels")
async def cb_default_levels(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    status = game_service.status(_chat_id(callback), callback_thread_id(callback))
    await callback.message.answer(
        "Выберите уровни, из которых рулетка будет брать карточки по умолчанию:",
        reply_markup=default_levels_menu(tuple(status.get("enabled_levels", (1, 2, 3, 4)))),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:default_level:"))
async def cb_default_level(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    status = game_service.status(_chat_id(callback), callback_thread_id(callback))
    selected = set(status.get("enabled_levels", (1, 2, 3, 4)))
    try:
        updated = game_service.set_enabled_level(
            _chat_id(callback),
            callback_thread_id(callback),
            level,
            level not in selected,
        )
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=default_levels_menu(updated))
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:timer:"))
async def cb_timer(callback: CallbackQuery, config: Config, timer_service: TimerService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    turn_id = int(callback.data.split(":")[-1])
    try:
        timer_id = timer_service.start_for_turn(turn_id, callback.from_user.id)
    except ValueError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    await callback.message.answer(
        "Таймер запущен. Бот сообщит, когда время закончится.",
        reply_markup=card_actions(turn_id, False),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:reset:yes")
async def cb_reset_yes(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    game_service.reset_session(_chat_id(callback), callback_thread_id(callback))
    await callback.message.answer("Сессия завершена.", reply_markup=main_menu())
    await answer_callback(callback)


@router.callback_query(F.data == "game:reset:no")
async def cb_reset_no(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await callback.message.answer(
        "Продолжаем.",
        reply_markup=_main_menu(game_service, _chat_id(callback), callback_thread_id(callback)),
    )
    await answer_callback(callback)
