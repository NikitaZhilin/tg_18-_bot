from __future__ import annotations

from app.services.admin_service import AdminService
from app.services.feedback_service import FeedbackService
from app.services.game_service import GameService
from tests.helpers import import_seed, make_config, migrated_db


def test_unclear_card_feedback_reaches_admin_queue(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    game = GameService(db, make_config(tmp_path))
    game.ensure_session(10, 7)
    game.accept_base_consent(10, 7, 111)
    game.accept_base_consent(10, 7, 222)
    result = game.draw_card(
        10,
        7,
        111,
        level=1,
        category="task",
        intensity="light",
    )

    feedback = FeedbackService(db)
    assert feedback.report_unclear(10, 7, result.turn_id, 111) is True
    assert feedback.report_unclear(10, 7, result.turn_id, 111) is False
    marked = db.fetchone(
        "SELECT review_status, is_enabled FROM cards WHERE id = ?",
        (result.card.id,),
    )
    assert marked["review_status"] == "needs_review"
    assert int(marked["is_enabled"]) == 0

    admin = AdminService(db)
    queue = admin.list_card_feedback()
    assert len(queue) == 1
    assert int(queue[0]["card_id"]) == result.card.id
    admin.approve_card(111, result.card.id)
    assert admin.list_card_feedback() == []
    approved = db.fetchone(
        "SELECT review_status, is_enabled FROM cards WHERE id = ?",
        (result.card.id,),
    )
    assert approved["review_status"] == "approved"
    assert int(approved["is_enabled"]) == 1
    db.close()
