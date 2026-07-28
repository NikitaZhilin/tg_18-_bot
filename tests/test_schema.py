from __future__ import annotations

from pathlib import Path

import pytest

from app.services.content_importer import ContentImporter
from app.services.game_service import GameService
from app.storage import Database
from tests.helpers import make_config, migrated_db


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
    row = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='card_review_progress'"
    )
    assert row["name"] == "card_review_progress"
    session_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(sessions)")}
    turn_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(turns)")}
    item_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(items)")}
    card_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(cards)")}
    session_item_columns = {row["name"] for row in db.fetchall("PRAGMA table_info(session_items)")}
    assert "current_player_slot" in session_columns
    assert "allow_restricted_content" in session_columns
    assert "allow_level_4" not in session_columns
    assert "max_intensity" not in session_columns
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
    assert applied["count"] >= 16
    assert db.fetchone(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'daily_consents'"
    ) is None
    db.close()


def test_failed_migration_is_rolled_back_with_its_version_record(tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_ok.sql").write_text(
        "CREATE TABLE stable_table (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    (migrations / "002_broken.sql").write_text(
        """
        CREATE TABLE partial_table (id INTEGER PRIMARY KEY);
        THIS IS NOT VALID SQL;
        """,
        encoding="utf-8",
    )
    db = Database(tmp_path / "migration-test.sqlite3")

    with pytest.raises(Exception):
        db.apply_migrations(migrations)

    assert db.fetchone(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'stable_table'"
    )
    assert db.fetchone(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'partial_table'"
    ) is None
    applied = {
        str(row["name"])
        for row in db.fetchall("SELECT name FROM schema_migrations ORDER BY name")
    }
    assert applied == {"001_ok.sql"}
    db.close()


def test_legacy_two_account_desire_owner_is_migrated_to_player_slot(tmp_path):
    old_migrations = tmp_path / "old-migrations"
    old_migrations.mkdir()
    project_root = Path(__file__).parents[1]
    migration_source = project_root / "app" / "storage" / "migrations"
    for migration in sorted(migration_source.glob("*.sql")):
        if migration.name >= "016_":
            continue
        (old_migrations / migration.name).write_bytes(migration.read_bytes())

    db = Database(tmp_path / "legacy.sqlite3")
    db.apply_migrations(old_migrations)
    ContentImporter(db).import_file(
        project_root / "content" / "cards.csv",
        dry_run=False,
    )
    game = GameService(db, make_config(tmp_path))
    session = game.ensure_session(10, None)
    desire_card = db.fetchone(
        "SELECT id FROM cards WHERE category = 'desire' ORDER BY id LIMIT 1"
    )
    desire_id = db.execute(
        """
        INSERT INTO saved_desires (session_id, card_id, owner_id, granted_by)
        VALUES (?, ?, 222, 111)
        """,
        (session["id"], desire_card["id"]),
    ).lastrowid

    db.apply_migrations(migration_source)

    migrated = db.fetchone(
        "SELECT owner_slot, granted_by_slot FROM saved_desires WHERE id = ?",
        (desire_id,),
    )
    assert dict(migrated) == {
        "owner_slot": "player_2",
        "granted_by_slot": "player_1",
    }
    db.close()
