from __future__ import annotations

from app.services.game_service import GameService
from app.services.safety_service import SafetyService
from app.services.timer_service import TimerService
from tests.helpers import import_seed, make_config, make_single_account_config, migrated_db


def enable_one_timed_card(db) -> None:
    db.execute("UPDATE cards SET is_enabled = 0")
    db.execute(
        "UPDATE cards SET is_enabled = 1 WHERE external_id = 'task_l1_015'"
    )


def test_stopword_stops_session_turn_and_timer(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    enable_one_timed_card(db)
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


def test_manual_reset_stops_turn_and_cancels_timer(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    enable_one_timed_card(db)
    game = GameService(db, make_config(tmp_path))
    game.ensure_session(10, None)
    game.accept_base_consent(10, None, 111)
    game.accept_base_consent(10, None, 222)
    result = game.draw_card(10, None, 111, level=1, category="task", intensity="light")
    TimerService(db).start_for_turn(result.turn_id, 111)

    game.reset_session(10, None)

    session = db.fetchone("SELECT status FROM sessions WHERE id = 1")
    turn = db.fetchone("SELECT status FROM turns WHERE id = ?", (result.turn_id,))
    timer = db.fetchone("SELECT status FROM timers WHERE turn_id = ?", (result.turn_id,))
    assert session["status"] == "reset"
    assert turn["status"] == "stopped"
    assert timer["status"] == "cancelled"
    db.close()


def test_single_account_consent_is_reused_for_new_session_on_same_day(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_single_account_config(tmp_path)
    game = GameService(db, config)
    game.ensure_session(10, None)
    assert game.accept_base_consent(10, None, 111) is False
    assert game.accept_base_consent(10, None, 111) is True

    safety = SafetyService(db)
    assert safety.stopword(10, None, 111) is True

    game.ensure_session(10, None)
    assert game.has_base_consent(10, None) is True
    active = game.active_session(10, None)
    assert active is not None
    assert db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM session_consents
        WHERE session_id = ?
          AND consent_type IN ('base_game:player_1', 'base_game:player_2')
          AND accepted = 1
        """,
        (active["id"],),
    )["count"] == 2
    db.close()
