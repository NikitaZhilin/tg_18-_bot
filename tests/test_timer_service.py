from __future__ import annotations

import asyncio

from app.services.game_service import GameService
from app.services.timer_service import TimerService
from tests.helpers import import_seed, make_config, migrated_db


def test_due_timer_sends_telegram_message(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    game = GameService(db, make_config(tmp_path))
    game.ensure_session(10, None)
    game.accept_base_consent(10, None, 111)
    game.accept_base_consent(10, None, 222)
    result = game.draw_card(10, None, 111, level=1, category="task", intensity="light")
    timer_service = TimerService(db)
    timer_id = timer_service.start_for_turn(result.turn_id, 111)
    db.execute("UPDATE timers SET deadline_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", timer_id))
    sent: list[tuple[int, str]] = []

    async def notify(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    asyncio.run(timer_service.process_due_timers(notify))

    timer = db.fetchone("SELECT * FROM timers WHERE id = ?", (timer_id,))
    assert sent == [(10, "Время вышло.")]
    assert timer["status"] == "completed"
    assert timer["notified_at"] is not None
    db.close()
