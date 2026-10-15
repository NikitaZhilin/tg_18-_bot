from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Config
from app.domain import PickFilter, PickedCard
from app.labels import CATEGORY_NAMES, INTENSITY_NAMES, LEVEL_NAMES
from app.services.card_picker import CardPicker, NoCardsAvailable
from app.services.errors import GameError
from app.services.session_settings import SessionSettingsMixin
from app.storage import Database
from app.storage.repositories.cards import CardRepository
from app.storage.repositories.sessions import SessionRepository
from app.storage.repositories.users import UserRepository


BASE_CONSENT_REQUIRED = "Нужно подтвердить согласие перед началом игры"


@dataclass(frozen=True)
class DrawResult:
    turn_id: int
    card: PickedCard
    play_mode: str | None = None


class GameService(SessionSettingsMixin):
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config
        self.sessions = SessionRepository(db)
        self.users = UserRepository(db)
        self.cards = CardRepository(db)
        self.card_picker = CardPicker(db)

    def _consent_date(self) -> str:
        return datetime.now(ZoneInfo(self.config.bot_timezone)).date().isoformat()

    def _restore_daily_consents(self, session: sqlite3.Row) -> None:
        daily_consents = self.sessions.daily_slot_consents(
            str(session["chat_key"]),
            self._consent_date(),
        )
        for consent in daily_consents:
            slot = str(consent["player_slot"])
            expected_user_id = int(session[f"{slot}_id"])
            if int(consent["user_id"]) == expected_user_id:
                self.sessions.add_consent(
                    int(session["id"]),
                    expected_user_id,
                    f"base_game:{slot}",
                    True,
                )

    def _player_label(self, slot: str) -> str:
        return self.config.player_2_name if slot == "player_2" else self.config.player_1_name

    def register_allowed_users(self) -> None:
        ids = sorted(self.config.allowed_user_ids)
        if not ids:
            return
        names = [self.config.player_1_name, self.config.player_2_name]
        roles = ["player_1", "player_2"]
        users_to_register = ids[:2]
        for index, user_id in enumerate(users_to_register):
            self.users.upsert_user(user_id, names[index] if index < len(names) else str(user_id), roles[index])

    def ensure_session(self, chat_id: int, thread_id: int | None, title: str | None = None) -> sqlite3.Row:
        self.register_allowed_users()
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        self.sessions.ensure_chat_context(chat_key, chat_id, thread_id, title)
        active = self.sessions.get_active(chat_key)
        if active:
            self._restore_daily_consents(active)
            return active
        player_1_id, player_2_id = self._players_for_chat(chat_id)
        session_id = self.sessions.create(
            chat_key,
            player_1_id,
            player_2_id,
            player_1_id,
            "player_1",
        )
        session = self.db.fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))
        self._restore_daily_consents(session)
        return session

    def _players_for_chat(self, chat_id: int) -> tuple[int, int]:
        """Who plays in this chat.

        A private chat with the bot belongs to its owner: both partners share one
        phone, so both player slots are that account. A group is played from two
        phones, so the two allowed accounts take turns there.
        """
        player_ids = sorted(self.config.allowed_user_ids)
        if chat_id > 0 and chat_id in self.config.allowed_user_ids:
            return chat_id, chat_id
        if len(player_ids) >= 2 and (chat_id < 0 or not self.config.single_account_two_players):
            return player_ids[0], player_ids[1]
        if self.config.single_account_two_players and player_ids:
            return player_ids[0], player_ids[0]
        if chat_id < 0:
            raise GameError(
                "Для игры в группе боту нужны два аккаунта: добавьте второй Telegram ID "
                "в ALLOWED_TELEGRAM_USER_IDS на сервере."
            )
        raise GameError("Нужно указать два ALLOWED_TELEGRAM_USER_IDS")

    def active_session(self, chat_id: int, thread_id: int | None) -> sqlite3.Row | None:
        return self.sessions.get_active(self.sessions.chat_key(chat_id, thread_id))

    def accept_base_consent(self, chat_id: int, thread_id: int | None, user_id: int) -> bool:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self._restore_daily_consents(session)
        next_slot = self.next_consent_slot(chat_id, thread_id)
        if next_slot is None:
            return True
        expected_user_id = int(session[f"{next_slot}_id"])
        if int(user_id) != expected_user_id:
            raise GameError(f"Сейчас подтверждает {self._player_label(next_slot)}")
        self.sessions.add_daily_slot_consent(
            str(session["chat_key"]),
            next_slot,
            user_id,
            self._consent_date(),
        )
        self.sessions.add_consent(
            int(session["id"]),
            user_id,
            f"base_game:{next_slot}",
            True,
        )
        return len(self.sessions.accepted_consent_slots(int(session["id"]))) == 2

    def next_consent_slot(self, chat_id: int, thread_id: int | None) -> str | None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self._restore_daily_consents(session)
        confirmed = self.sessions.accepted_consent_slots(int(session["id"]))
        for slot in ("player_1", "player_2"):
            if slot not in confirmed:
                return slot
        return None

    def next_consent_label(self, chat_id: int, thread_id: int | None) -> str | None:
        slot = self.next_consent_slot(chat_id, thread_id)
        return self._player_label(slot) if slot else None

    def has_base_consent(self, chat_id: int, thread_id: int | None) -> bool:
        if not self.config.require_daily_consent:
            return True
        session = self.active_session(chat_id, thread_id)
        if not session:
            return False
        self._restore_daily_consents(session)
        return len(self.sessions.accepted_consent_slots(int(session["id"]))) == 2

    def draw_card(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
        *,
        level: int | None,
        category: str | None,
        intensity: str | None = None,
        source: str = "manual",
        collection_code: str | None = None,
        play_mode: str | None = None,
    ) -> DrawResult:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session:
                raise GameError("Нет активной сессии")
            if (
                self.config.require_daily_consent
                and len(self.sessions.accepted_consent_slots(int(session["id"]))) < 2
            ):
                raise GameError(BASE_CONSENT_REQUIRED)
            if int(session["current_player_id"]) != int(user_id):
                raise GameError(f"Сейчас очередь: {self._player_label(session['current_player_slot'])}")
            if session["active_turn_id"]:
                raise GameError("Сначала завершите текущую карточку или откройте ее кнопкой «Продолжить карточку»")
            if source == "penalty" and not bool(session["allow_penalties"]):
                raise GameError("Штрафы не включены в настройках сессии")
            if source == "penalty":
                category = "penalty"
            if collection_code == "restricted_content":
                if not bool(session["allow_restricted_content"]):
                    raise GameError("Сначала откройте доступ к разделу «Экстрим» в админке")
                level = None
                intensity = None

            turn_number = int(
                conn.execute(
                    "SELECT COALESCE(MAX(turn_number), 0) + 1 AS num FROM turns WHERE session_id = ?",
                    (session["id"],),
                ).fetchone()["num"]
            )
            current_slot = session["current_player_slot"] or "player_1"
            levels: tuple[int, ...] | None = None
            if level is None and collection_code is None:
                selected_levels = list(self.sessions.enabled_levels(int(session["id"])))
                if not selected_levels:
                    raise GameError("В настройке уровней по умолчанию не осталось доступных разделов")
                levels = tuple(selected_levels)

            card = self.card_picker.pick(
                PickFilter(
                    session_id=int(session["id"]),
                    level=level,
                    levels=levels,
                    category=category,
                    intensity=intensity,
                    collection_code=collection_code,
                    allow_restricted_content=bool(session["allow_restricted_content"]),
                ),
                conn,
            )
            cur = conn.execute(
                """
                INSERT INTO turns (
                    session_id, turn_number, player_id, card_id, source, status,
                    selected_level, selected_category, selected_intensity, player_slot,
                    selected_item_code, selected_collection_code, play_mode
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["id"],
                    turn_number,
                    user_id,
                    card.id,
                    source,
                    level,
                    category,
                    intensity,
                    current_slot,
                    card.selected_item_code,
                    collection_code,
                    play_mode,
                ),
            )
            turn_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO used_cards (session_id, card_id, turn_id, used_by)
                VALUES (?, ?, ?, ?)
                """,
                (session["id"], card.id, turn_id, user_id),
            )
            if card.category == "desire":
                other_slot = "player_2" if current_slot == "player_1" else "player_1"
                other_player = (
                    session["player_2_id"]
                    if other_slot == "player_2"
                    else session["player_1_id"]
                )
                conn.execute(
                    """
                    INSERT INTO saved_desires (
                        session_id, card_id, owner_id, granted_by, owner_slot, granted_by_slot
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session["id"], card.id, user_id, other_player, current_slot, other_slot),
                )
            conn.execute(
                "UPDATE sessions SET active_turn_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (turn_id, session["id"]),
            )
        return DrawResult(turn_id, card, play_mode)

    def replace_active_card(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
    ) -> DrawResult:
        result = self._replace_active_card(
            chat_id,
            thread_id,
            user_id,
            revision_turn_id=None,
            allow_no_replacement=False,
        )
        if result is None:  # pragma: no cover - normal replacement always raises instead
            raise NoCardsAvailable("no matching cards")
        return result

    def request_card_revision(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
        turn_id: int,
    ) -> DrawResult | None:
        return self._replace_active_card(
            chat_id,
            thread_id,
            user_id,
            revision_turn_id=turn_id,
            allow_no_replacement=True,
        )

    def _replace_active_card(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
        *,
        revision_turn_id: int | None,
        allow_no_replacement: bool,
    ) -> DrawResult | None:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        replacement: PickedCard | None = None
        new_turn_id: int | None = None
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session or not session["active_turn_id"]:
                raise GameError("Активной карточки нет")
            turn = conn.execute(
                "SELECT * FROM turns WHERE id = ?",
                (session["active_turn_id"],),
            ).fetchone()
            if not turn:
                raise GameError("Активной карточки нет")
            if int(turn["player_id"]) != int(user_id):
                raise GameError("Сейчас ход другого игрока")
            if revision_turn_id is not None and int(turn["id"]) != int(revision_turn_id):
                raise GameError("Эта карточка уже обработана")
            level = turn["selected_level"]
            category = turn["selected_category"]
            intensity = turn["selected_intensity"]
            source = turn["source"]
            collection_code = turn["selected_collection_code"]
            levels: tuple[int, ...] | None = None
            if level is None and collection_code is None:
                levels = self.sessions.enabled_levels(int(session["id"]))
                if not levels:
                    raise GameError("В настройке уровней по умолчанию не осталось доступных разделов")
            try:
                replacement = self.card_picker.pick(
                    PickFilter(
                        session_id=int(session["id"]),
                        level=int(level) if level is not None else None,
                        levels=levels,
                        category=category,
                        intensity=intensity,
                        collection_code=collection_code,
                        allow_restricted_content=bool(session["allow_restricted_content"]),
                    ),
                    conn,
                )
            except NoCardsAvailable:
                if not allow_no_replacement:
                    raise

            if revision_turn_id is not None:
                card_id = int(turn["card_id"])
                self.cards.save_version(
                    card_id,
                    user_id,
                    "player_requested_revision",
                    conn,
                )
                self.cards.set_status(card_id, "needs_review", False, conn)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO card_feedback (
                        card_id, session_id, turn_id, reported_by, player_slot
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        card_id,
                        session["id"],
                        turn["id"],
                        user_id,
                        turn["player_slot"],
                    ),
                )
            turn_number = int(
                conn.execute(
                    "SELECT COALESCE(MAX(turn_number), 0) + 1 AS num FROM turns WHERE session_id = ?",
                    (session["id"],),
                ).fetchone()["num"]
            )
            conn.execute(
                "UPDATE turns SET status = 'skipped', finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (turn["id"],),
            )
            conn.execute(
                """
                UPDATE timers
                SET status = 'cancelled',
                    claim_token = NULL,
                    claim_until = NULL
                WHERE turn_id = ? AND status = 'active'
                """,
                (turn["id"],),
            )
            conn.execute(
                """
                DELETE FROM saved_desires
                WHERE session_id = ? AND card_id = ? AND status = 'saved'
                """,
                (session["id"], turn["card_id"]),
            )
            if replacement is None:
                conn.execute(
                    """
                    UPDATE sessions
                    SET active_turn_id = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (session["id"],),
                )
                return None
            conn.execute(
                """
                INSERT INTO turns (
                    session_id, turn_number, player_id, card_id, source, status,
                    selected_level, selected_category, selected_intensity, player_slot,
                    selected_item_code, selected_collection_code, play_mode
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["id"],
                    turn_number,
                    user_id,
                    replacement.id,
                    source,
                    level,
                    category,
                    intensity,
                    turn["player_slot"],
                    replacement.selected_item_code,
                    collection_code,
                    turn["play_mode"],
                ),
            )
            new_turn_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
            conn.execute(
                """
                INSERT INTO used_cards (session_id, card_id, turn_id, used_by)
                VALUES (?, ?, ?, ?)
                """,
                (session["id"], replacement.id, new_turn_id, user_id),
            )
            if replacement.category == "desire":
                owner_slot = str(turn["player_slot"])
                other_slot = "player_2" if owner_slot == "player_1" else "player_1"
                other_player = session["player_2_id"] if other_slot == "player_2" else session["player_1_id"]
                conn.execute(
                    """
                    INSERT INTO saved_desires (
                        session_id, card_id, owner_id, granted_by, owner_slot, granted_by_slot
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session["id"], replacement.id, user_id, other_player, owner_slot, other_slot),
                )
            conn.execute(
                "UPDATE sessions SET active_turn_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_turn_id, session["id"]),
            )
        if replacement is None or new_turn_id is None:  # pragma: no cover - guarded above
            return None
        return DrawResult(new_turn_id, replacement, turn["play_mode"])

    def draw_truth_or_dare(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
        *,
        level: int,
        intensity: str,
        category: str,
    ) -> DrawResult:
        """«Правда» = question, «Действие» = task of the chosen level.

        Questions are few, so when they run out at this intensity the bot takes
        one from another intensity of the same level.
        """
        if category not in ("question", "task"):
            raise GameError("Неизвестный выбор")
        kwargs = dict(level=level, category=category, play_mode=f"tod:{level}:{intensity}")
        try:
            return self.draw_card(chat_id, thread_id, user_id, intensity=intensity, **kwargs)
        except NoCardsAvailable:
            if category != "question":
                raise
            return self.draw_card(chat_id, thread_id, user_id, intensity=None, **kwargs)

    def turn_play_mode(self, turn_id: int) -> str | None:
        row = self.db.fetchone("SELECT play_mode FROM turns WHERE id = ?", (turn_id,))
        return str(row["play_mode"]) if row and row["play_mode"] else None

    def current_card(self, chat_id: int, thread_id: int | None) -> DrawResult | None:
        session = self.active_session(chat_id, thread_id)
        if not session or not session["active_turn_id"]:
            return None
        card = self.card_picker.for_turn(int(session["active_turn_id"]))
        if not card:
            return None
        turn_id = int(session["active_turn_id"])
        return DrawResult(turn_id, card, self.turn_play_mode(turn_id))

    def refuse_card(self, chat_id: int, thread_id: int | None, user_id: int, turn_id: int) -> DrawResult | None:
        """Refusing a card costs a penalty card of the same level.

        Returns the penalty, or None when no penalty is left: then the card is
        simply closed and the other player goes next.
        """
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session or not session["active_turn_id"]:
                raise GameError("Активной карточки нет")
            if int(session["active_turn_id"]) != int(turn_id):
                raise GameError("Эта карточка уже обработана")
            turn = conn.execute("SELECT * FROM turns WHERE id = ?", (turn_id,)).fetchone()
            if not turn or turn["status"] != "active":
                raise GameError("Карточка уже завершена")
            if int(turn["player_id"]) != int(user_id):
                raise GameError("Сейчас очередь другого игрока")
            card = conn.execute("SELECT level, category FROM cards WHERE id = ?", (turn["card_id"],)).fetchone()
            if card["category"] == "penalty":
                raise GameError("От штрафа отказаться нельзя 😈")
            conn.execute(
                "UPDATE turns SET status = 'skipped', finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (turn_id,),
            )
            conn.execute(
                "UPDATE timers SET status = 'cancelled', claim_token = NULL, claim_until = NULL "
                "WHERE turn_id = ? AND status = 'active'",
                (turn_id,),
            )
            level = int(card["level"])
            penalty = None
            for filters in (
                dict(level=level),
                dict(levels=tuple(range(1, level + 1))),
                # Forfeits may repeat once all of them were played.
                dict(level=level, allow_repeats=True),
            ):
                try:
                    penalty = self.card_picker.pick(
                        PickFilter(
                            session_id=int(session["id"]),
                            category="penalty",
                            allow_restricted_content=False,
                            **filters,
                        ),
                        conn,
                    )
                    break
                except NoCardsAvailable:
                    continue
            if penalty is None:
                current_slot = session["current_player_slot"] or "player_1"
                next_slot = "player_2" if current_slot == "player_1" else "player_1"
                next_player = session["player_2_id"] if next_slot == "player_2" else session["player_1_id"]
                conn.execute(
                    "UPDATE sessions SET active_turn_id = NULL, current_player_id = ?, current_player_slot = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (next_player, next_slot, session["id"]),
                )
                return None
            turn_number = int(
                conn.execute(
                    "SELECT COALESCE(MAX(turn_number), 0) + 1 AS num FROM turns WHERE session_id = ?",
                    (session["id"],),
                ).fetchone()["num"]
            )
            cur = conn.execute(
                """
                INSERT INTO turns (
                    session_id, turn_number, player_id, card_id, source, status,
                    selected_level, selected_category, selected_intensity, player_slot,
                    selected_item_code, selected_collection_code, play_mode
                )
                VALUES (?, ?, ?, ?, 'penalty', 'active', ?, 'penalty', NULL, ?, ?, NULL, ?)
                """,
                (
                    session["id"],
                    turn_number,
                    user_id,
                    penalty.id,
                    level,
                    turn["player_slot"],
                    penalty.selected_item_code,
                    turn["play_mode"],
                ),
            )
            new_turn_id = int(cur.lastrowid)
            conn.execute(
                "INSERT OR IGNORE INTO used_cards (session_id, card_id, turn_id, used_by) VALUES (?, ?, ?, ?)",
                (session["id"], penalty.id, new_turn_id, user_id),
            )
            conn.execute(
                "UPDATE sessions SET active_turn_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_turn_id, session["id"]),
            )
        return DrawResult(new_turn_id, penalty, turn["play_mode"])

    def finish_turn(self, chat_id: int, thread_id: int | None, user_id: int, status: str = "completed") -> str:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session:
                raise GameError("Нет активной сессии")
            active_turn_id = session["active_turn_id"]
            if not active_turn_id:
                raise GameError("Активной карточки нет")
            turn = conn.execute(
                "SELECT player_id, status FROM turns WHERE id = ?",
                (active_turn_id,),
            ).fetchone()
            if not turn or turn["status"] != "active":
                raise GameError("Карточка уже завершена")
            if int(turn["player_id"]) != int(user_id):
                raise GameError("Сейчас ход другого игрока")
            conn.execute(
                "UPDATE turns SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, active_turn_id),
            )
            conn.execute(
                """
                UPDATE timers
                SET status = 'cancelled', claim_token = NULL, claim_until = NULL
                WHERE turn_id = ? AND status = 'active'
                """,
                (active_turn_id,),
            )
            current_slot = session["current_player_slot"] or "player_1"
            next_slot = "player_2" if current_slot == "player_1" else "player_1"
            next_player = session["player_2_id"] if next_slot == "player_2" else session["player_1_id"]
            conn.execute(
                """
                UPDATE sessions
                SET current_player_id = ?,
                    current_player_slot = ?,
                    active_turn_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_player, next_slot, session["id"]),
            )
        return self._player_label(next_slot)

    def unlock_restricted_content(self, chat_id: int, thread_id: int | None) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.set_restricted_content(int(session["id"]), True)

    def disable_restricted_content(self, chat_id: int, thread_id: int | None) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.set_restricted_content(int(session["id"]), False)

    def reset_session(self, chat_id: int, thread_id: int | None) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE turns
                SET status = 'stopped', finished_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND status IN ('selecting', 'active')
                """,
                (session["id"],),
            )
            conn.execute(
                """
                UPDATE timers
                SET status = 'cancelled', claim_token = NULL, claim_until = NULL
                WHERE session_id = ? AND status = 'active'
                """,
                (session["id"],),
            )
            conn.execute(
                """
                UPDATE sessions
                SET status = 'reset',
                    stop_reason = 'manual_reset',
                    stopped_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (session["id"],),
            )

    def status(self, chat_id: int, thread_id: int | None) -> dict[str, object]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return {"active": False}
        used = self.db.fetchone("SELECT COUNT(*) AS count FROM used_cards WHERE session_id = ?", (session["id"],))["count"]
        timer = self.db.fetchone(
            "SELECT * FROM timers WHERE session_id = ? AND status = 'active' ORDER BY deadline_at LIMIT 1",
            (session["id"],),
        )
        return {
            "active": True,
            "session_id": session["id"],
            "current_player_id": session["current_player_id"],
            "current_player_slot": session["current_player_slot"],
            "current_player_label": self._player_label(session["current_player_slot"]),
            "used_cards": used,
            "active_timer": timer["deadline_at"] if timer else None,
            "restricted_content": bool(session["allow_restricted_content"]),
            "enabled_levels": self.sessions.enabled_levels(int(session["id"])),
            "has_active_turn": bool(session["active_turn_id"]),
            "active_turn_id": session["active_turn_id"],
            "anal_mode": self.anal_mode(chat_id, thread_id),
            "saved_desires": int(
                self.db.fetchone(
                    "SELECT COUNT(*) AS count FROM saved_desires WHERE session_id = ? AND status = 'saved'",
                    (session["id"],),
                )["count"]
            ),
        }

    def categories_with_cards(self, level: int, intensity: str) -> list[str]:
        """Categories that have at least one playable card, so the menu shows no dead buttons."""
        rows = self.db.fetchall(
            """
            SELECT DISTINCT c.category
            FROM cards c
            WHERE c.is_enabled = 1
              AND c.review_status = 'approved'
              AND c.is_archived = 0
              AND c.deleted_at IS NULL
              AND c.level = ?
              AND c.intensity = ?
              AND NOT EXISTS (
                  SELECT 1 FROM card_collection_items restricted
                  WHERE restricted.card_id = c.id
                    AND restricted.collection_code = 'restricted_content'
              )
            """,
            (level, intensity),
        )
        return [str(row["category"]) for row in rows]


def format_card(card: PickedCard) -> str:
    from app.keyboards.game import LEVEL_ICONS

    if card.collection_code == "restricted_content":
        section = "🔞 Экстрим"
    else:
        section = f"{LEVEL_ICONS.get(card.level, '')} {LEVEL_NAMES[card.level]}".strip()
    intensity = f" · {INTENSITY_NAMES[card.intensity]}" if card.level >= 3 else ""
    title = f"{section}{intensity} · {CATEGORY_NAMES[card.category]} №{card.display_number}"
    heading = f"\n«{card.title}»" if getattr(card, "title", "") else ""
    item = ""
    if card.required_items:
        item_lines = []
        for name, usage in card.required_items:
            item_lines.append(f"• {name}")
            if usage:
                item_lines.append(f"  {usage}")
        item = "\n\n🧸 Понадобится:\n" + "\n".join(item_lines)
    if card.selected_item_name:
        item = f"\n\n🧸 Бонус к карточке: {card.selected_item_name}."
        if card.selected_item_usage:
            item += f"\n{card.selected_item_usage}"
    minutes, seconds = divmod(card.timer_seconds or 0, 60)
    if card.timer_seconds:
        duration = f"{minutes} мин" + (f" {seconds} сек" if seconds else "") if minutes else f"{seconds} сек"
        timer = f"\n\n⏱ {duration} — нажмите «Запустить таймер», бот напомнит."
    else:
        timer = ""
    return f"{title}{heading}\n\n{card.text}{item}{timer}"
