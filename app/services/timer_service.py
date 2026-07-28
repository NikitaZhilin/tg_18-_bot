from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.storage import Database
from app.storage.repositories.timers import TimerRepository

logger = logging.getLogger(__name__)


class TimerService:
    def __init__(self, db: Database):
        self.db = db
        self.timers = TimerRepository(db)

    def start_for_turn(self, turn_id: int, started_by: int) -> int:
        turn = self.db.fetchone(
            """
            SELECT t.*, c.timer_seconds
            FROM turns t
            JOIN cards c ON c.id = t.card_id
            JOIN sessions s ON s.id = t.session_id
            WHERE t.id = ?
              AND t.status = 'active'
              AND s.status IN ('draft', 'active')
            """,
            (turn_id,),
        )
        if not turn:
            raise ValueError("Карточка уже завершена или недоступна")
        if int(turn["player_id"]) != int(started_by):
            raise ValueError("Таймер может запустить только текущий игрок")
        if not turn["timer_seconds"]:
            raise ValueError("У этой карточки нет таймера")
        existing = self.timers.active_for_turn(turn_id)
        if existing:
            return int(existing["id"])
        return self.timers.create(
            int(turn["session_id"]),
            turn_id,
            int(turn["card_id"]),
            started_by,
            int(turn["timer_seconds"]),
        )

    async def process_due_timers(
        self,
        notify: Callable[[int, str, int | None], Awaitable[None]],
    ) -> None:
        for timer in self.timers.due():
            session = self.db.fetchone("SELECT chat_key FROM sessions WHERE id = ?", (timer["session_id"],))
            if session:
                chat_raw, thread_raw = str(session["chat_key"]).split(":", 1)
                thread_id = int(thread_raw) or None
                await notify(int(chat_raw), "Время вышло.", thread_id)
                self.timers.mark_completed(int(timer["id"]))

    async def run_due_loop(
        self,
        notify: Callable[[int, str, int | None], Awaitable[None]],
        *,
        poll_seconds: int = 5,
    ) -> None:
        while True:
            try:
                await self.process_due_timers(notify)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("timer runner failed")
            await asyncio.sleep(poll_seconds)
