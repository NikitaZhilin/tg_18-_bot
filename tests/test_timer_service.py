from __future__ import annotations

import asyncio

import pytest

from app.services.game_service import GameService
from app.services.timer_service import TimerService
from tests.helpers import import_seed, make_config, migrated_db


def enable_one_timed_card(db) -> None:
    db.execute("UPDATE cards SET is_enabled = 0")
    db.execute(
        "UPDATE cards SET is_enabled = 1 WHERE external_id = 'task_l1_015'"
    )


def test_due_timer_sends_telegram_message(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    enable_one_timed_card(db)
    game = GameService(db, make_config(tmp_path))
    game.ensure_session(10, 77)
    game.accept_base_consent(10, 77, 111)
    game.accept_base_consent(10, 77, 222)
    result = game.draw_card(10, 77, 111, level=1, category="task", intensity="light")
    timer_service = TimerService(db)
    timer_id = timer_service.start_for_turn(result.turn_id, 111)
    db.execute("UPDATE timers SET deadline_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", timer_id))
    sent: list[tuple[int, str, int | None]] = []

    async def notify(chat_id: int, text: str, thread_id: int | None) -> None:
        sent.append((chat_id, text, thread_id))

    asyncio.run(timer_service.process_due_timers(notify))

    timer = db.fetchone("SELECT * FROM timers WHERE id = ?", (timer_id,))
    assert sent == [(10, "Время вышло.", 77)]
    assert timer["status"] == "completed"
    assert timer["notified_at"] is not None
    db.close()


def test_failed_timer_notification_is_retried_later(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    enable_one_timed_card(db)
    game = GameService(db, make_config(tmp_path))
    game.ensure_session(10, None)
    game.accept_base_consent(10, None, 111)
    game.accept_base_consent(10, None, 222)
    result = game.draw_card(10, None, 111, level=1, category="task", intensity="light")
    timer_service = TimerService(db)
    timer_id = timer_service.start_for_turn(result.turn_id, 111)
    db.execute("UPDATE timers SET deadline_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", timer_id))

    async def failed_notify(chat_id: int, text: str, thread_id: int | None) -> None:
        raise RuntimeError("temporary Telegram error")

    try:
        asyncio.run(timer_service.process_due_timers(failed_notify))
    except RuntimeError:
        pass

    timer = db.fetchone("SELECT status, notified_at FROM timers WHERE id = ?", (timer_id,))
    assert timer["status"] == "active"
    assert timer["notified_at"] is None
    db.close()


def test_timer_requires_active_turn_and_current_player(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    enable_one_timed_card(db)
    game = GameService(db, make_config(tmp_path))
    game.ensure_session(10, None)
    game.accept_base_consent(10, None, 111)
    game.accept_base_consent(10, None, 222)
    result = game.draw_card(10, None, 111, level=1, category="task", intensity="light")
    timer_service = TimerService(db)

    with pytest.raises(ValueError, match="текущий игрок"):
        timer_service.start_for_turn(result.turn_id, 222)

    timer_id = timer_service.start_for_turn(result.turn_id, 111)
    game.finish_turn(10, None, 111)
    timer = db.fetchone("SELECT status FROM timers WHERE id = ?", (timer_id,))
    assert timer["status"] == "cancelled"
    with pytest.raises(ValueError, match="завершена"):
        timer_service.start_for_turn(result.turn_id, 111)
    db.close()
