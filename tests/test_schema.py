from __future__ import annotations

from tests.helpers import migrated_db


def test_schema_loads(tmp_path):
    db = migrated_db(tmp_path)
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'")
    assert row["name"] == "cards"
    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_actions'")
    assert row["name"] == "admin_actions"
    db.close()
