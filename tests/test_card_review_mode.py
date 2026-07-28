from __future__ import annotations

from app.services.admin_service import AdminService
from tests.helpers import import_seed, migrated_db


def test_review_mode_persists_progress_and_reopens_edited_card(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute(
        "INSERT INTO users (telegram_id, display_name, role) VALUES (111, 'Админ', 'player_1')"
    )
    db.execute(
        "INSERT INTO users (telegram_id, display_name, role) VALUES (222, 'Другой админ', 'player_2')"
    )
    service = AdminService(db)

    reviewed, total = service.review_progress(111)
    assert reviewed == 0
    assert total > 1

    first = service.get_next_review_card(111)
    assert first is not None
    first_id = int(first["id"])
    service.mark_reviewed_ok(111, first_id)

    reviewed, unchanged_total = service.review_progress(111)
    assert reviewed == 1
    assert unchanged_total == total
    assert int(service.get_next_review_card(111)["id"]) != first_id
    assert service.review_progress(222) == (0, total)
    assert int(service.get_next_review_card(222)["id"]) == first_id

    service.update_card_field(
        111,
        first_id,
        "text",
        str(first["text"]) + "\nУточненная версия.",
    )
    assert int(service.get_next_review_card(111)["id"]) == first_id
    db.close()


def test_review_mode_marks_card_for_revision_and_queue_lists_it(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    db.execute(
        "INSERT INTO users (telegram_id, display_name, role) VALUES (111, 'Админ', 'player_1')"
    )
    service = AdminService(db)
    card = service.get_next_review_card(111)
    assert card is not None
    card_id = int(card["id"])

    service.mark_card_for_revision(111, card_id)

    marked = service.get_card(card_id)
    assert marked["review_status"] == "needs_review"
    assert int(marked["is_enabled"]) == 0
    assert service.count_revision_cards() == 1
    assert [int(row["id"]) for row in service.list_revision_cards()] == [card_id]
    reviewed, total = service.review_progress(111)
    assert reviewed == 1
    assert total > 1

    service.reset_review_progress(111)
    assert service.review_progress(111)[0] == 0
    db.close()
