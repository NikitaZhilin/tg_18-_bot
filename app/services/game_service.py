from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.config import Config
from app.domain import PickFilter, PickedCard
from app.services.card_picker import CardPicker, NoCardsAvailable
from app.storage import Database
from app.storage.repositories.sessions import SessionRepository
from app.storage.repositories.users import UserRepository


class GameError(RuntimeError):
    pass


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

    def register_allowed_users(self) -> None:
        ids = sorted(self.config.allowed_user_ids)
        if not ids:
            return
        names = [self.config.player_1_name, self.config.player_2_name]
        roles = ["player_1", "player_2"]
        for index, user_id in enumerate(ids[:2]):
            self.users.upsert_user(user_id, names[index] if index < len(names) else str(user_id), roles[index])

    def ensure_session(self, chat_id: int, thread_id: int | None, title: str | None = None) -> sqlite3.Row:
        self.register_allowed_users()
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        self.sessions.ensure_chat_context(chat_key, chat_id, thread_id, title)
        active = self.sessions.get_active(chat_key)
        if active:
            return active
        player_ids = sorted(self.config.allowed_user_ids)
        if len(player_ids) < 2:
            raise GameError("Нужно указать два ALLOWED_TELEGRAM_USER_IDS")
        session_id = self.sessions.create(
            chat_key,
            player_ids[0],
            player_ids[1],
            player_ids[0],
            self.config.allow_level_4_default,
        )
        return self.db.fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))

    def active_session(self, chat_id: int, thread_id: int | None) -> sqlite3.Row | None:
        return self.sessions.get_active(self.sessions.chat_key(chat_id, thread_id))

    def set_items_for_active_session(self, chat_id: int, thread_id: int | None, item_codes: list[str]) -> None:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.set_items(int(session["id"]), item_codes)

    def accept_base_consent(self, chat_id: int, thread_id: int | None, user_id: int) -> bool:
        session = self.active_session(chat_id, thread_id)
        if not session:
            raise GameError("Нет активной сессии")
        self.sessions.add_consent(int(session["id"]), user_id, "base_game", True)
        return self.sessions.accepted_count(int(session["id"]), "base_game") >= 2

    def items_for_active_session(self, chat_id: int, thread_id: int | None) -> set[str]:
        session = self.active_session(chat_id, thread_id)
        if not session:
            return set()
        return {
            row["item_code"]
            for row in self.db.fetchall(
                "SELECT item_code FROM session_items WHERE session_id = ?",
                (session["id"],),
            )
        }

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
        if self.sessions.accepted_count(int(session["id"]), "hard_intensity") >= 2:
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
        if self.sessions.accepted_count(int(session["id"]), "level_4") >= 2:
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
    ) -> DrawResult:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session:
                raise GameError("Нет активной сессии")
            if self.sessions.accepted_count(int(session["id"]), "base_game") < 2:
                raise GameError("Нужно базовое подтверждение обоих игроков")
            if int(session["current_player_id"]) != int(user_id):
                raise GameError("Сейчас ход другого игрока")
            if level == 4 and not bool(session["allow_level_4"]):
                raise GameError("Уровень 4 нужно включить отдельным согласием обоих игроков")
            if intensity == "hard" and session["max_intensity"] != "hard":
                raise GameError("Жесткую интенсивность нужно включить отдельным согласием обоих игроков")
            if source == "penalty" and not bool(session["allow_penalties"]):
                raise GameError("Штрафы не включены в настройках сессии")
            if source == "penalty":
                category = "penalty"

            turn_number = int(
                conn.execute(
                    "SELECT COALESCE(MAX(turn_number), 0) + 1 AS num FROM turns WHERE session_id = ?",
                    (session["id"],),
                ).fetchone()["num"]
            )
            picker_max_intensity = session["max_intensity"]
            if source == "manual" and intensity in {"light", "medium"}:
                picker_max_intensity = intensity

            card = self.card_picker.pick(
                PickFilter(
                    session_id=int(session["id"]),
                    level=level,
                    category=category,
                    intensity=intensity,
                    allow_level_4=bool(session["allow_level_4"]),
                    max_intensity=picker_max_intensity,
                ),
                conn,
            )
            cur = conn.execute(
                """
                INSERT INTO turns (
                    session_id, turn_number, player_id, card_id, source, status,
                    selected_level, selected_category, selected_intensity
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (session["id"], turn_number, user_id, card.id, source, level, category, intensity),
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

    def finish_turn(self, chat_id: int, thread_id: int | None, user_id: int, status: str = "completed") -> None:
        chat_key = self.sessions.chat_key(chat_id, thread_id)
        with self.db.transaction() as conn:
            session = self.sessions.get_active(chat_key, conn)
            if not session:
                raise GameError("Нет активной сессии")
            active_turn_id = session["active_turn_id"]
            if active_turn_id:
                conn.execute(
                    "UPDATE turns SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, active_turn_id),
                )
            next_player = session["player_2_id"] if int(session["current_player_id"]) == int(session["player_1_id"]) else session["player_1_id"]
            conn.execute(
                """
                UPDATE sessions
                SET current_player_id = ?, active_turn_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_player, session["id"]),
            )

    def reset_session(self, chat_id: int, thread_id: int | None) -> None:
        session = self.active_session(chat_id, thread_id)
        if session:
            self.sessions.finish_session(int(session["id"]), "reset", "manual_reset")

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
            "used_cards": used,
            "active_timer": timer["deadline_at"] if timer else None,
            "allow_level_4": bool(session["allow_level_4"]),
            "max_intensity": session["max_intensity"],
        }


def format_card(card: PickedCard) -> str:
    title = f"{card.title}\n\n" if card.title else ""
    timer = f"\n\nТаймер: {card.timer_seconds} сек." if card.timer_seconds else ""
    aftercare = "\n\nПосле карточки нужен короткий check-in/aftercare." if card.aftercare_required else ""
    return f"{title}{card.text}{timer}{aftercare}"
