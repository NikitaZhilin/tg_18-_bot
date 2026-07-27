from __future__ import annotations

from pathlib import Path

from app.config import Config
from app.services.content_importer import ContentImporter
from app.storage import Database


def make_config(tmp_path: Path) -> Config:
    return Config(
        bot_token="",
        allowed_user_ids={111, 222},
        admin_user_ids={111, 222},
        player_1_name="A",
        player_2_name="B",
        bot_timezone="Europe/Moscow",
        data_dir=tmp_path,
        database_path=tmp_path / "bot.sqlite3",
        log_level="INFO",
        dry_run=True,
        allow_unlisted_users=False,
        allow_level_4_default=False,
        telegram_proxy_url=None,
    )


def migrated_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "bot.sqlite3")
    db.apply_migrations()
    return db


def import_seed(db: Database) -> None:
    report = ContentImporter(db).import_file(Path("content/cards.csv"), dry_run=False)
    assert report.warnings_count == 0
