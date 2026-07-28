from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.config import Config
from app.domain import PickFilter, PickedCard
from app.labels import CATEGORY_NAMES, INTENSITY_NAMES, LEVEL_NAMES
from app.services.card_picker import CardPicker, NoCardsAvailable
from app.storage import Database
from app.storage.repositories.sessions import SessionRepository
from app.storage.repositories.users import UserRepository


class GameError(RuntimeError):
    pass


BASE_CONSENT_REQUIRED = "Нужно подтвердить согласие перед началом игры"


@dataclass(frozen=True)
class DrawResult:
    turn_id: int
    card: PickedCard


class GameService:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config
        self.sessions = SessionRepository(db)
        self.users = UserRepository(db)
        self.card_picker = CardPicker(db)

    def _is_single_account_session(self, session: sqlite3.Row) -> bool:
        return int(session["player_1_id"]) == int(session["player_2_id"])

    def _required_consent_count(self, session: sqlite3.Row) -> int:
        return 1 if self._is_single_account_session(session) else 2

    def _player_label(self, slot: str) -> str:
        return self.config.player_2_name if slot == "player_2" else self.config.player_1_name

    def register_allowed_users(self) -> None:
        ids = sorted(self.config.allowed_user_ids)
        if not ids:
            return
        names = [self.config.player_1_name, self.config.player_2_name]
        roles = ["player_1", "player_2"]
        users_to_register = ids[:1] if self.config.single_account_two_players else ids[:2]
        for index, user_id in enumerate(users_to_register):
            self.users.upsert_user(user_id, names[index] if index < len(names) else str(user_id), roles[index])

    def ensure_session(self, chat_id: int, thread_id: int | None, title: str | None = None) -> sqlite3.Row:
        self.register_allowed_users()
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        self.sessions.ensure_chat_context(chat_key, chat_id, thread_id, title)
        active = self.sessions.get_active(chat_key)
        if active:
            return active
        player_ids = sorted(self.config.allowed_user_ids)
        if self.config.single_account_two_players:
            if not player_ids:
                raise GameError("Нужно указать ALLOWED_TELEGRAM_USER_IDS")
            player_1_id = player_ids[0]
            player_2_id = player_ids[0]
        elif len(player_ids) < 2:
            raise GameError("Нужно указать два ALLOWED_TELEGRAM_USER_IDS")
        else:
            player_1_id = player_ids[0]
            player_2_id = player_ids[1]
        session_id = self.sessions.create(
            chat_key,
            player_1_id,
            player_2_id,
            player_1_id,
            self.config.allow_level_4_default,
            "player_1",
        )
        return self.db.fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))

    def active_session(self, chat_id: int, thread_id: int | None) -> sqlite3.Row | None:
        return self.sessions.get_active(self.sessions.chat_key(chat_id, thread_id))

    def set_items_for_active_session(self, chat_id: int, thread_id: int | None, items: dict[str, int]) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.set_items(int(session["id"]), items)

    def accept_base_consent(self, chat_id: int, thread_id: int | None, user_id: int) -> bool:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.add_consent(int(session["id"]), user_id, "base_game", True)
        return self.sessions.accepted_count(int(session["id"]), "base_game") >= self._required_consent_count(session)

    def items_for_active_session(self, chat_id: int, thread_id: int | None) -> dict[str, int]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return {}
        return {
            row["item_code"]: int(row["frequency"])
            for row in self.db.fetchall(
                "SELECT item_code, frequency FROM session_items WHERE session_id = ?",
                (session["id"],),
            )
        }

    def available_items(self) -> list[sqlite3.Row]:
        return self.db.fetchall(
            """
            SELECT code, name
            FROM items
            WHERE is_active = 1
              AND is_archived = 0
              AND deleted_at IS NULL
            ORDER BY name
            """
        )

    def enabled_levels(self, chat_id: int, thread_id: int | None) -> tuple[int, ...]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return ()
        return self.sessions.enabled_levels(int(session["id"]))

    def set_enabled_level(
        self,
        chat_id: int,
        thread_id: int | None,
        level: int,
        enabled: bool,
    ) -> tuple[int, ...]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        current = set(self.sessions.enabled_levels(int(session["id"])))
        if enabled:
            current.add(level)
        else:
            current.discard(level)
        if not current:
            raise GameError("Нужно оставить включенным хотя бы один уровень")
        self.sessions.set_enabled_level(int(session["id"]), level, enabled)
        return tuple(sorted(current))

    def has_base_consent(self, chat_id: int, thread_id: int | None) -> bool:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return False
        return self.sessions.accepted_count(int(session["id"]), "base_game") >= self._required_consent_count(session)

    def set_boundaries_for_active_session(self, chat_id: int, thread_id: int | None, risk_tags: list[str], user_id: int | None = None) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.set_blocked_tags(int(session["id"]), risk_tags)
        self.db.execute(
            """
            INSERT INTO safety_events (session_id, user_id, event_type, details)
            VALUES (?, ?, 'boundary_updated', ?)
            """,
            (session["id"], user_id, ",".join(risk_tags)),
        )

    def boundaries_for_active_session(self, chat_id: int, thread_id: int | None) -> set[str]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return set()
        return {
            row["risk_tag"]
            for row in self.db.fetchall(
                "SELECT risk_tag FROM session_blocked_tags WHERE session_id = ?",
                (session["id"],),
            )
        }

    def set_hard_consent(self, chat_id: int, thread_id: int | None, user_id: int, accepted: bool) -> bool:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.add_consent(int(session["id"]), user_id, "hard_intensity", accepted)
        if not accepted:
            self.sessions.set_max_intensity(int(session["id"]), "medium")
            self.db.execute(
                """
                INSERT INTO safety_events (session_id, user_id, event_type)
                VALUES (?, ?, 'hard_disabled')
                """,
                (int(session["id"]), user_id),
            )
            return False
        if self.sessions.accepted_count(int(session["id"]), "hard_intensity") >= self._required_consent_count(session):
            self.sessions.set_max_intensity(int(session["id"]), "hard")
            self.db.execute(
                """
                INSERT INTO safety_events (session_id, user_id, event_type)
                VALUES (?, ?, 'hard_enabled')
                """,
                (int(session["id"]), user_id),
            )
            return True
        return False

    def set_level_4_consent(self, chat_id: int, thread_id: int | None, user_id: int, accepted: bool) -> bool:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.add_consent(int(session["id"]), user_id, "level_4", accepted)
        if not accepted:
            self.sessions.set_level_4(int(session["id"]), False)
            self.db.execute(
                """
                INSERT INTO safety_events (session_id, user_id, event_type)
                VALUES (?, ?, 'level_4_disabled')
                """,
                (int(session["id"]), user_id),
            )
            return False
        if self.sessions.accepted_count(int(session["id"]), "level_4") >= self._required_consent_count(session):
            self.sessions.set_level_4(int(session["id"]), True)
            self.db.execute(
                """
                INSERT INTO safety_events (session_id, user_id, event_type)
                VALUES (?, ?, 'level_4_enabled')
                """,
                (int(session["id"]), user_id),
            )
            return True
        return False

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
    ) -> DrawResult:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session:
                raise GameError("Нет активной сессии")
            if self.sessions.accepted_count(int(session["id"]), "base_game") < self._required_consent_count(session):
                raise GameError(BASE_CONSENT_REQUIRED)
            if int(session["current_player_id"]) != int(user_id):
                raise GameError("Сейчас ход другого игрока")
            if session["active_turn_id"]:
                raise GameError("Сначала завершите текущую карточку или откройте ее кнопкой «Продолжить карточку»")
            if level == 4 and not bool(session["allow_level_4"]):
                raise GameError("Уровень 4 нужно включить отдельным согласием")
            if intensity == "hard" and session["max_intensity"] != "hard":
                raise GameError("Жесткую интенсивность нужно включить отдельным согласием")
            if source == "penalty" and not bool(session["allow_penalties"]):
                raise GameError("Штрафы не включены в настройках сессии")
            if source == "penalty":
                category = "penalty"
            if collection_code == "restricted_content":
                if not bool(session["allow_restricted_content"]):
                    raise GameError("Сначала откройте доступ к разделу «Экстрим» в админке")
                if not bool(session["allow_level_4"]) or session["max_intensity"] != "hard":
                    raise GameError("Для раздела «Экстрим» включите BDSM и жесткую интенсивность")
                level = None
                intensity = None

            turn_number = int(
                conn.execute(
                    "SELECT COALESCE(MAX(turn_number), 0) + 1 AS num FROM turns WHERE session_id = ?",
                    (session["id"],),
                ).fetchone()["num"]
            )
            picker_max_intensity = session["max_intensity"]
            if intensity in {"light", "medium"}:
                picker_max_intensity = intensity
            elif source == "roulette" and level is not None and session["max_intensity"] != "hard":
                picker_max_intensity = "medium"
            current_slot = session["current_player_slot"] or "player_1"
            levels: tuple[int, ...] | None = None
            if level is None and collection_code is None:
                selected_levels = list(self.sessions.enabled_levels(int(session["id"])))
                if not bool(session["allow_level_4"]):
                    selected_levels = [value for value in selected_levels if value != 4]
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
                    allow_level_4=bool(session["allow_level_4"]),
                    max_intensity=picker_max_intensity,
                    allow_restricted_content=bool(session["allow_restricted_content"]),
                ),
                conn,
            )
            cur = conn.execute(
                """
                INSERT INTO turns (
                    session_id, turn_number, player_id, card_id, source, status,
                    selected_level, selected_category, selected_intensity, player_slot,
                    selected_item_code, selected_collection_code
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
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
                other_player = session["player_2_id"] if int(user_id) == int(session["player_1_id"]) else session["player_1_id"]
                conn.execute(
                    """
                    INSERT INTO saved_desires (session_id, card_id, owner_id, granted_by)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session["id"], card.id, user_id, other_player),
                )
            conn.execute(
                "UPDATE sessions SET active_turn_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (turn_id, session["id"]),
            )
        return DrawResult(turn_id, card)

    def replace_active_card(
        self,
        chat_id: int,
        thread_id: int | None,
        user_id: int,
    ) -> DrawResult:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
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
            conn.execute(
                "UPDATE turns SET status = 'skipped', finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (turn["id"],),
            )
            conn.execute(
                """
                UPDATE timers
                SET status = 'cancelled'
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
            conn.execute(
                "UPDATE sessions SET active_turn_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session["id"],),
            )
            level = turn["selected_level"]
            category = turn["selected_category"]
            intensity = turn["selected_intensity"]
            source = turn["source"]
            collection_code = turn["selected_collection_code"]
        return self.draw_card(
            chat_id,
            thread_id,
            user_id,
            level=int(level) if level is not None else None,
            category=category,
            intensity=intensity,
            source=source,
            collection_code=collection_code,
        )

    def current_card(self, chat_id: int, thread_id: int | None) -> DrawResult | None:
        session = self.active_session(chat_id, thread_id)
        if not session or not session["active_turn_id"]:
            return None
        card = self.card_picker.for_turn(int(session["active_turn_id"]))
        if not card:
            return None
        return DrawResult(int(session["active_turn_id"]), card)

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
                "UPDATE timers SET status = 'cancelled' WHERE turn_id = ? AND status = 'active'",
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
                "UPDATE timers SET status = 'cancelled' WHERE session_id = ? AND status = 'active'",
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
            "allow_level_4": bool(session["allow_level_4"]),
            "max_intensity": session["max_intensity"],
            "restricted_content": bool(session["allow_restricted_content"]),
            "enabled_levels": self.sessions.enabled_levels(int(session["id"])),
            "has_active_turn": bool(session["active_turn_id"]),
        }


def format_card(card: PickedCard) -> str:
    section = "Экстрим" if card.collection_code == "restricted_content" else LEVEL_NAMES[card.level]
    title = f"{section} · {CATEGORY_NAMES[card.category]} №{card.display_number}"
    intensity = f"\nИнтенсивность: {INTENSITY_NAMES[card.intensity]}" if card.level >= 3 else ""
    item = ""
    if card.required_items:
        item_lines = []
        for name, usage in card.required_items:
            item_lines.append(f"• {name}")
            if usage:
                item_lines.append(f"  {usage}")
        item = "\n\nОбязательный реквизит:\n" + "\n".join(item_lines)
    if card.selected_item_name:
        item = f"\n\nРеквизит для этой карточки: {card.selected_item_name}."
        if card.selected_item_usage:
            item += f"\n{card.selected_item_usage}"
    timer = f"\n\nТаймер: {card.timer_seconds} сек." if card.timer_seconds else ""
    aftercare = (
        "\n\nПосле задания: полностью остановитесь, устройтесь удобно и по очереди скажите, "
        "что было комфортно, что стоит изменить и что не нужно повторять."
        if card.aftercare_required
        else ""
    )
    return f"{title}{intensity}\n\nЧто нужно сделать:\n{card.text}{item}{timer}{aftercare}"
