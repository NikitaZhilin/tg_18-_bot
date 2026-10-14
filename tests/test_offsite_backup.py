from __future__ import annotations

import gzip
import sqlite3
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.send_backup_telegram import build_archive, caption, recipients
from tests.helpers import make_config

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))


def test_backup_goes_only_to_owners(tmp_path):
    assert recipients(make_config(tmp_path)) == [111, 222]


def test_refuses_to_send_database_to_many_recipients(tmp_path):
    config = replace(make_config(tmp_path), admin_user_ids={1, 2, 3, 4})
    with pytest.raises(SystemExit, match="refusing"):
        recipients(config)


def test_refuses_without_owners(tmp_path):
    with pytest.raises(SystemExit, match="empty"):
        recipients(replace(make_config(tmp_path), admin_user_ids=set()))


def test_archive_is_a_restorable_database(tmp_path):
    source = tmp_path / "bot.sqlite3"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES ('ok')")
    workdir = tmp_path / "work"
    archive = build_archive(source, workdir, NOW)
    assert archive.name == "tg18-backup-20261018-1200.sqlite3.gz"
    restored = tmp_path / "restored.sqlite3"
    restored.write_bytes(gzip.decompress(archive.read_bytes()))
    with sqlite3.connect(restored) as conn:
        assert conn.execute("SELECT v FROM t").fetchone()[0] == "ok"
    assert [p.name for p in workdir.iterdir()] == [archive.name]


def test_caption_has_date_and_warning():
    text = caption(NOW)
    assert "18.10.2026 12:00" in text
    assert "не пересылайте" in text
