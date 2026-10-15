from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Config
from app.handlers.common import answer_callback, callback_thread_id, reject_callback_if_not_allowed
from app.handlers.screens import close_card, home, show_screen
from app.keyboards.game import (
    card_actions,
    category_menu,
    consent_menu,
    default_levels_menu,
    end_game_confirm,
    category_menu_text,
    intensity_menu,
    intensity_menu_text,
    level_menu,
    level_menu_text,
    settings_menu,
    settings_menu_text,
    tod_choice_menu,
    tod_choice_text,
    tod_intensity_menu,
    tod_level_menu,
    tod_level_text,
)
from app.services.card_picker import NoCardsAvailable
from app.services.game_service import BASE_CONSENT_REQUIRED, DrawResult, GameError, GameService, format_card
from app.services.safety_service import SafetyService
from app.services.timer_service import TimerService

router = Router(name="game")

NO_CARDS_TEXT = (
    "Здесь карточек больше нет. Либо все уже сыграны в этой игре, "
    "либо для оставшихся нужен реквизит, который не отмечен в «⚙️ Настройки → 🧸 Игрушки и реквизит»."
)
CARD_CLOSED_TEXT = "Эта карточка уже закрыта."


def _chat_id(callback: CallbackQuery) -> int:
    if not callback.message:
        raise GameError("Нет сообщения")
    return callback.message.chat.id


def _where(callback: CallbackQuery) -> tuple[int, int | None]:
    return _chat_id(callback), callback_thread_id(callback)


def _turn_id_from(data: str) -> int | None:
    """game:done:42 -> 42; old buttons without an id (game:done) -> None."""
    tail = data.split(":")[2:] if data.count(":") >= 2 else []
    return int(tail[0]) if tail and tail[0].isdigit() else None


async def _show_home(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    chat_id, thread_id = _where(callback)
    text, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
    await show_screen(callback, text, markup)


async def _send_home(callback: CallbackQuery, config: Config, game_service: GameService, prefix: str) -> None:
    chat_id, thread_id = _where(callback)
    text, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
    await callback.bot.send_message(
        chat_id,
        f"{prefix}\n\n{text}",
        reply_markup=markup,
        message_thread_id=thread_id,
    )


def _threesome(game_service: GameService, callback: CallbackQuery) -> bool:
    return bool(game_service.status(*_where(callback)).get("threesome"))


def _level_menu(game_service: GameService, chat_id: int, thread_id: int | None):
    status = game_service.status(chat_id, thread_id)
    return level_menu(restricted_enabled=bool(status.get("restricted_content", False)))


def _card_markup(result: DrawResult, has_timer: bool | None = None):
    return card_actions(
        result.turn_id,
        bool(result.card.timer_seconds) if has_timer is None else has_timer,
        is_penalty=result.card.category == "penalty",
    )


async def _show_card(callback: CallbackQuery, result: DrawResult, prefix: str = "") -> None:
    await show_screen(callback, prefix + format_card(result.card), _card_markup(result))


async def _show_game_error(callback: CallbackQuery, exc: GameError) -> None:
    if str(exc) == BASE_CONSENT_REQUIRED:
        await show_screen(callback, "Перед первой карточкой подтвердите согласие на игру.", consent_menu())
        await answer_callback(callback)
        return
    await answer_callback(callback, str(exc), show_alert=True)


async def _no_cards(callback: CallbackQuery, game_service: GameService) -> None:
    chat_id, thread_id = _where(callback)
    await show_screen(callback, NO_CARDS_TEXT, _level_menu(game_service, chat_id, thread_id))
    await answer_callback(callback)


async def _card_is_stale(callback: CallbackQuery, game_service: GameService) -> bool:
    """Buttons of an old card must not act on the card that is open now."""
    turn_id = _turn_id_from(callback.data or "")
    if turn_id is None:
        return False
    status = game_service.status(*_where(callback))
    if status.get("active_turn_id") == turn_id:
        return False
    await close_card(callback, "Карточка закрыта.")
    await answer_callback(callback, CARD_CLOSED_TEXT, show_alert=True)
    return True


@router.callback_query(F.data == "game:home")
async def cb_game_home(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    message = callback.message
    if message is not None and getattr(message, "reply_markup", None) and _is_card_message(message):
        # «В меню» from a card keeps the card on screen and opens the menu below it.
        await _send_home(callback, config, game_service, "▶️ Карточка остаётся открытой — вернуться к ней можно из меню.")
    else:
        await _show_home(callback, config, game_service)
    await answer_callback(callback)


def _is_penalty_message(message) -> bool:
    markup = getattr(message, "reply_markup", None)
    rows = getattr(markup, "inline_keyboard", None) or []
    datas = [button.callback_data or "" for row in rows for button in row]
    return any(d.startswith("game:done") for d in datas) and not any(d.startswith("game:refuse") for d in datas)


def _is_card_message(message) -> bool:
    markup = getattr(message, "reply_markup", None)
    rows = getattr(markup, "inline_keyboard", None) or []
    return any((button.callback_data or "").startswith("game:done") for row in rows for button in row)


@router.callback_query(F.data == "game:settings")
async def cb_settings(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    chat_id, thread_id = _where(callback)
    try:
        game_service.ensure_session(chat_id, thread_id, callback.message.chat.title if callback.message else None)
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    status = game_service.status(chat_id, thread_id)
    await show_screen(
        callback,
        settings_menu_text(),
        settings_menu(tuple(status.get("enabled_levels") or (1, 2, 3, 4))),
    )
    await answer_callback(callback)


@router.callback_query(F.data == "game:current")
async def cb_current_card(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    result = game_service.current_card(*_where(callback))
    if not result:
        await answer_callback(callback, "Незавершенной карточки нет.", show_alert=True)
        return
    await _show_card(callback, result)
    await answer_callback(callback)


@router.callback_query(F.data == "game:menu")
async def cb_game_menu(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    chat_id, thread_id = _where(callback)
    try:
        game_service.ensure_session(chat_id, thread_id, callback.message.chat.title if callback.message else None)
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    if not game_service.has_base_consent(chat_id, thread_id):
        player_name = game_service.next_consent_label(chat_id, thread_id)
        await show_screen(
            callback,
            f"Перед первой карточкой согласие подтверждает {player_name}.",
            consent_menu(player_name),
        )
        await answer_callback(callback)
        return
    await show_screen(callback, level_menu_text(), _level_menu(game_service, chat_id, thread_id))
    await answer_callback(callback)


@router.callback_query(F.data == "game:base_consent")
async def cb_base_consent(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    chat_id, thread_id = _where(callback)
    try:
        game_service.ensure_session(chat_id, thread_id, callback.message.chat.title if callback.message else None)
        ready = game_service.accept_base_consent(chat_id, thread_id, callback.from_user.id)
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    if ready:
        text, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
        await show_screen(callback, f"Оба подтверждения получены. Можно начинать.\n\n{text}", markup)
    else:
        next_player = game_service.next_consent_label(chat_id, thread_id)
        await show_screen(
            callback,
            f"Подтверждение записано. Теперь подтверждает {next_player}.",
            consent_menu(next_player),
        )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:level:"))
async def cb_level(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    if level >= 3:
        await show_screen(callback, intensity_menu_text(level), intensity_menu(level))
    else:
        categories = game_service.categories_with_cards(level, "light", _threesome(game_service, callback))
        await show_screen(
            callback,
            category_menu_text(level, "light", categories),
            category_menu(level, "light", categories),
        )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:intensity:"))
async def cb_intensity(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity = callback.data.split(":")
    categories = game_service.categories_with_cards(int(level), intensity, _threesome(game_service, callback))
    await show_screen(
        callback,
        category_menu_text(int(level), intensity, categories),
        category_menu(int(level), intensity, categories),
    )
    await answer_callback(callback)


def _ensure_game(callback: CallbackQuery, game_service: GameService) -> None:
    chat_id, thread_id = _where(callback)
    game_service.ensure_session(chat_id, thread_id, callback.message.chat.title if callback.message else None)


async def _draw(callback: CallbackQuery, game_service: GameService, **kwargs) -> None:
    chat_id, thread_id = _where(callback)
    tod = kwargs.pop("truth_or_dare", None)
    try:
        _ensure_game(callback, game_service)
        if tod:
            result = game_service.draw_truth_or_dare(chat_id, thread_id, callback.from_user.id, **tod)
        else:
            result = game_service.draw_card(chat_id, thread_id, callback.from_user.id, **kwargs)
    except NoCardsAvailable:
        if tod:
            what = "вопросы" if tod["category"] == "question" else "задания"
            await answer_callback(
                callback,
                f"На этом уровне {what} в этой игре закончились. Выберите другое или смените уровень.",
                show_alert=True,
            )
            return
        if kwargs.get("collection_code") == "restricted_content":
            await answer_callback(callback, "В разделе «Экстрим» не осталось подходящих карточек.", show_alert=True)
            return
        await _no_cards(callback, game_service)
        return
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    await _show_card(callback, result)
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:category:"))
async def cb_category(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity, category = callback.data.split(":")
    await _draw(callback, game_service, level=int(level), category=category, intensity=intensity)


@router.callback_query(F.data == "game:roulette")
async def cb_roulette(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await _draw(callback, game_service, level=None, category=None, intensity=None, source="roulette")


@router.callback_query(F.data == "game:extreme")
async def cb_extreme(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await _draw(
        callback,
        game_service,
        level=None,
        category=None,
        intensity=None,
        source="roulette",
        collection_code="restricted_content",
    )


@router.callback_query(F.data.startswith("game:roulette_level:"))
async def cb_roulette_level(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity = callback.data.split(":")
    await _draw(
        callback,
        game_service,
        level=int(level),
        category=None,
        intensity=None if intensity == "any" else intensity,
        source="roulette",
    )


@router.callback_query(F.data.startswith("game:done"))
async def cb_done(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    if await _card_is_stale(callback, game_service):
        return
    chat_id, thread_id = _where(callback)
    status = game_service.status(chat_id, thread_id)
    turn_id = status.get("active_turn_id")
    play_mode = game_service.turn_play_mode(int(turn_id)) if turn_id else None
    try:
        next_player = game_service.finish_turn(chat_id, thread_id, callback.from_user.id, "completed")
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    await close_card(callback, "✅ Сделано")
    tod = _parse_tod_mode(play_mode)
    if tod:
        level, intensity = tod
        await callback.bot.send_message(
            chat_id,
            tod_choice_text(level, intensity, next_player),
            reply_markup=tod_choice_menu(level, intensity),
            message_thread_id=thread_id,
        )
    else:
        await _send_home(callback, config, game_service, f"✅ Готово! Теперь очередь: {next_player}.")
    await answer_callback(callback)


def _parse_tod_mode(play_mode: str | None) -> tuple[int, str] | None:
    """'tod:3:medium' -> (3, 'medium')."""
    parts = (play_mode or "").split(":")
    if len(parts) == 3 and parts[0] == "tod" and parts[1].isdigit():
        return int(parts[1]), parts[2]
    return None


@router.callback_query(F.data.startswith("game:replace"))
@router.callback_query(F.data == "game:skip")
async def cb_replace_card(
    callback: CallbackQuery,
    config: Config,
    game_service: GameService,
    safety_service: SafetyService,
) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    if await _card_is_stale(callback, game_service):
        return
    chat_id, thread_id = _where(callback)
    session = game_service.active_session(chat_id, thread_id)
    session_id = int(session["id"]) if session else None
    turn_id = int(session["active_turn_id"]) if session and session["active_turn_id"] else None
    try:
        result = game_service.replace_active_card(chat_id, thread_id, callback.from_user.id)
    except NoCardsAvailable:
        await answer_callback(
            callback,
            "Другой подходящей карточки по этим условиям нет. Текущая карточка сохранена.",
            show_alert=True,
        )
        return
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    if session_id:
        safety_service.safe_skip(session_id, turn_id, callback.from_user.id)
    await _show_card(callback, result, "🔄 Другая карточка:\n\n")
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
    if await _card_is_stale(callback, game_service):
        return
    turn_id = int(callback.data.split(":")[-1])
    chat_id, thread_id = _where(callback)
    session = game_service.active_session(chat_id, thread_id)
    session_id = int(session["id"]) if session else None
    try:
        replacement = game_service.request_card_revision(chat_id, thread_id, callback.from_user.id, turn_id)
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    if session_id:
        safety_service.safe_skip(session_id, turn_id, callback.from_user.id)
    if replacement is None:
        text, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
        await show_screen(
            callback,
            "🚫 Карточка убрана из игры и отправлена в админку на доработку. "
            f"Другой с теми же условиями сейчас нет.\n\n{text}",
            markup,
        )
        await answer_callback(callback)
        return
    await _show_card(callback, replacement, "🚫 Прошлая карточка убрана. Вот другая:\n\n")
    await answer_callback(callback)


@router.callback_query(F.data == "game:default_levels")
async def cb_default_levels(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    status = game_service.status(*_where(callback))
    await show_screen(
        callback,
        "🎲 Из каких уровней брать случайную карточку? Нажмите, чтобы включить или выключить.",
        default_levels_menu(tuple(status.get("enabled_levels") or (1, 2, 3, 4))),
    )
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:default_level:"))
async def cb_default_level(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    chat_id, thread_id = _where(callback)
    status = game_service.status(chat_id, thread_id)
    selected = set(status.get("enabled_levels") or (1, 2, 3, 4))
    try:
        updated = game_service.set_enabled_level(chat_id, thread_id, level, level not in selected)
    except GameError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=default_levels_menu(updated))
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:refuse:"))
async def cb_refuse(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    if await _card_is_stale(callback, game_service):
        return
    chat_id, thread_id = _where(callback)
    turn_id = int(callback.data.split(":")[-1])
    play_mode = game_service.turn_play_mode(turn_id)
    try:
        penalty = game_service.refuse_card(chat_id, thread_id, callback.from_user.id, turn_id)
    except GameError as exc:
        await _show_game_error(callback, exc)
        return
    if penalty is not None:
        await close_card(callback, "🙅 Отказ")
        await callback.bot.send_message(
            chat_id,
            "🙅 Отказ — значит штраф:\n\n" + format_card(penalty.card),
            reply_markup=_card_markup(penalty),
            message_thread_id=thread_id,
        )
        await answer_callback(callback)
        return
    await close_card(callback, "🙅 Отказ")
    next_player = game_service.status(chat_id, thread_id).get("current_player_label")
    tod = _parse_tod_mode(play_mode)
    if tod:
        await callback.bot.send_message(
            chat_id,
            "Штрафы на этом уровне закончились, отказ засчитан без штрафа.\n\n" + tod_choice_text(*tod, next_player),
            reply_markup=tod_choice_menu(*tod),
            message_thread_id=thread_id,
        )
    else:
        await _send_home(callback, config, game_service, f"Штрафы закончились, отказ засчитан без штрафа. Теперь очередь: {next_player}.")
    await answer_callback(callback)


@router.callback_query(F.data.startswith("game:timer:"))
async def cb_timer(callback: CallbackQuery, config: Config, timer_service: TimerService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    turn_id = int(callback.data.split(":")[-1])
    try:
        timer_service.start_for_turn(turn_id, callback.from_user.id)
    except ValueError as exc:
        await answer_callback(callback, str(exc), show_alert=True)
        return
    try:
        markup = card_actions(turn_id, False, is_penalty=_is_penalty_message(callback.message))
        await callback.message.edit_reply_markup(reply_markup=markup)
    except Exception:
        pass
    await answer_callback(callback, "⏱ Таймер пошёл. Бот напишет, когда время выйдет.")


@router.callback_query(F.data == "game:reset:yes")
async def cb_reset_yes(
    callback: CallbackQuery,
    config: Config,
    game_service: GameService,
    safety_service: SafetyService,
) -> None:
    # Buttons from older versions of /reset: same as «Завершить игру».
    if await reject_callback_if_not_allowed(callback, config):
        return
    chat_id, thread_id = _where(callback)
    safety_service.end_game(chat_id, thread_id, callback.from_user.id)
    text, markup = home(game_service, config, chat_id, thread_id, callback.from_user.id)
    await show_screen(callback, f"Игра завершена.\n\n{text}", markup)
    await answer_callback(callback)


@router.callback_query(F.data == "game:reset:no")
async def cb_reset_no(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await _show_home(callback, config, game_service)
    await answer_callback(callback)


# ---- «Правда или действие» ----

@router.callback_query(F.data == "tod:menu")
async def cb_tod_menu(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    await show_screen(callback, tod_level_text(), tod_level_menu())
    await answer_callback(callback)


@router.callback_query(F.data.startswith("tod:level:"))
async def cb_tod_level(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    level = int(callback.data.split(":")[-1])
    if level >= 3:
        await show_screen(callback, intensity_menu_text(level), tod_intensity_menu(level))
    else:
        await _show_tod_choice(callback, game_service, level, "light")
    await answer_callback(callback)


@router.callback_query(F.data.startswith("tod:pick:"))
async def cb_tod_pick(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity = callback.data.split(":")
    await _show_tod_choice(callback, game_service, int(level), intensity)
    await answer_callback(callback)


async def _show_tod_choice(callback: CallbackQuery, game_service: GameService, level: int, intensity: str) -> None:
    status = game_service.status(*_where(callback))
    await show_screen(
        callback,
        tod_choice_text(level, intensity, status.get("current_player_label") if status.get("active") else None),
        tod_choice_menu(level, intensity),
    )


@router.callback_query(F.data.startswith("tod:draw:"))
async def cb_tod_draw(callback: CallbackQuery, config: Config, game_service: GameService) -> None:
    if await reject_callback_if_not_allowed(callback, config):
        return
    _, _, level, intensity, category = callback.data.split(":")
    await _draw(
        callback,
        game_service,
        truth_or_dare=dict(level=int(level), intensity=intensity, category=category),
    )
