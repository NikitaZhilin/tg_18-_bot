from __future__ import annotations

import pytest

from app.services.desire_service import DesireError, DesireService
from app.services.game_service import GameService
from tests.helpers import import_seed, make_single_account_config, migrated_db


def test_single_account_desire_tracks_virtual_owner_and_can_be_used_on_owner_turn(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_single_account_config(tmp_path)
    game = GameService(db, config)
    desires = DesireService(db, config)
    game.ensure_session(10, None)
    game.accept_base_consent(10, None, 111)
    game.accept_base_consent(10, None, 111)

    drawn = game.draw_card(10, None, 111, level=2, category="desire", intensity="light")
    saved = db.fetchone("SELECT * FROM saved_desires WHERE card_id = ?", (drawn.card.id,))
    assert saved["owner_id"] == 111
    assert saved["granted_by"] == 111
    assert saved["owner_slot"] == "player_1"
    assert saved["granted_by_slot"] == "player_2"
    game.finish_turn(10, None, 111)

    with pytest.raises(DesireError, match="Игрок 1"):
        desires.use_saved(10, None, int(saved["id"]), 111)

    second = game.draw_card(10, None, 111, level=1, category="task", intensity="light")
    assert second.card.category == "task"
    game.finish_turn(10, None, 111)

    used = desires.use_saved(10, None, int(saved["id"]), 111)
    assert used["owner_slot"] == "player_1"
    stored = db.fetchone("SELECT status, used_at FROM saved_desires WHERE id = ?", (saved["id"],))
    assert stored["status"] == "used"
    assert stored["used_at"] is not None
    assert desires.count_saved(10, None) == 0
    db.close()
