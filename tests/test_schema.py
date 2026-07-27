from __future__ import annotations

from tests.helpers import migrated_db


def test_schema_loads(tmp_path):
    db = migrated_db(tmp_path)
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'")
    assert row["name"] == "cards"
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_actions'")
    assert row["name"] == "admin_actions"
    session_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(sessions)")}
    turn_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(turns)")}
    assert "current_player_slot" in session_columns
    assert "allow_restricted_content" in session_columns
    assert "player_slot" in turn_columns
    db.apply_migrations()
    applied = db.fetchone("SELECT COUNT(*) AS count FROM schema_migrations")
    assert applied["count"] >= 3
    db.close()
