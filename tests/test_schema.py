from __future__ import annotations

from tests.helpers import migrated_db


def test_schema_loads(tmp_path):
    db = migrated_db(tmp_path)
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'")
    assert row["name"] == "cards"
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_actions'")
    assert row["name"] == "admin_actions"
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='fsm_states'")
    assert row["name"] == "fsm_states"
    row = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='session_setting_drafts'"
    )
    assert row["name"] == "session_setting_drafts"
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='seed_conflicts'")
    assert row["name"] == "seed_conflicts"
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='card_feedback'")
    assert row["name"] == "card_feedback"
    session_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(sessions)")}
    turn_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(turns)")}
    item_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(items)")}
    card_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(cards)")}
    session_item_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(session_items)")}
    assert "current_player_slot" in session_columns
    assert "allow_restricted_content" in session_columns
    assert "player_slot" in turn_columns
    assert "selected_item_code" in turn_columns
    assert "selected_collection_code" in turn_columns
    assert {"min_level", "max_level", "categories", "usage_text", "randomizable"}.issubset(item_columns)
    assert {"is_archived", "deleted_at"}.issubset(item_columns)
    assert {"item_mode", "is_archived", "deleted_at"}.issubset(card_columns)
    assert "frequency" in session_item_columns
    cuffs = db.fetchone(
        "SELECT name, min_level, max_level, randomizable FROM items WHERE code = 'soft_cuffs'"
    )
    assert dict(cuffs) == {
        "name": "Мягкие манжеты",
        "min_level": 4,
        "max_level": 4,
        "randomizable": 0,
    }
    db.apply_migrations()
    applied = db.fetchone("SELECT COUNT(*) AS count FROM schema_migrations")
    assert applied["count"] >= 15
    db.close()
