from __future__ import annotations

from app.services.game_service import GameService
from app.services.safety_service import SafetyService
from app.services.timer_service import TimerService
from tests.helpers import import_seed, make_config, migrated_db


def test_stopword_stops_session_turn_and_timer(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    game = GameService(db, make_config(tmp_path))
    game.ensure_session(10, None)
    game.accept_base_consent(10, None, 111)
    game.accept_base_consent(10, None, 222)
    result = game.draw_card(10, None, 111, level=1, category="task", intensity="light")
    TimerService(db).start_for_turn(result.turn_id, 111)
    stopped = SafetyService(db).stopword(10, None, 111)
    assert stopped is True
    session = db.fetchone("SELECT * FROM sessions WHERE id = 1")
    turn = db.fetchone("SELECT * FROM turns WHERE id = ?", (result.turn_id,))
    timer = db.fetchone("SELECT * FROM timers WHERE turn_id = ?", (result.turn_id,))
    event = db.fetchone("SELECT * FROM safety_events WHERE event_type = 'stopword'")
    assert session["status"] == "stopped"
    assert turn["status"] == "stopped"
    assert timer["status"] == "cancelled"
    assert event is not None
    db.close()
