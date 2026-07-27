from __future__ import annotations

from tests.helpers import import_restricted_seed, import_seed, migrated_db


def test_seed_content_counts_match_tz(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    rows = db.fetchall(
        """
        SELECT level, COUNT(*) AS count
        FROM cards
        WHERE category = 'task'
        GROUP BY level
        ORDER BY level
        """
    )
    assert [(row["level"], row["count"]) for row in rows] == [(1, 24), (2, 24), (3, 48), (4, 48)]
    pose_count = db.fetchone("SELECT COUNT(*) AS count FROM cards WHERE category = 'pose'")["count"]
    assert pose_count == 36
    db.close()


def test_hard_and_level4_seed_cards_require_review(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    row = db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM cards
        WHERE (level = 4 OR intensity = 'hard')
          AND (review_status = 'approved' OR is_enabled = 1)
        """
    )
    assert row["count"] == 0
    db.close()


def test_restricted_content_imports_into_closed_collection(tmp_path):
    db = migrated_db(tmp_path)
    import_restricted_seed(db)
    row = db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM cards c
        JOIN card_collection_items cci ON cci.card_id = c.id
        WHERE cci.collection_code = 'restricted_content'
          AND c.review_status = 'approved'
          AND c.is_enabled = 1
        """
    )
    assert row["count"] == 12
    db.close()
