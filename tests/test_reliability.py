from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import replace
from datetime import UTC, datetime

from app.services.error_report import (
    TELEGRAM_TEXT_LIMIT,
    ReportThrottle,
    build_admin_report,
)
from scripts.scheduled_backup import make_backup
from tests.helpers import make_config, make_single_account_config


def _raise_deep(depth: int):
    if depth == 0:
        raise ValueError("bad <module> & data " + "x" * 5000)
    _raise_deep(depth - 1)


def test_admin_report_fits_one_telegram_message_and_keeps_markup_chars():
    try:
        _raise_deep(60)
    except ValueError as exc:
        report = build_admin_report(exc, "кнопка 'game:draw'")
    assert len(report) <= TELEGRAM_TEXT_LIMIT
    assert report.startswith("Ошибка в боте")
    assert "<module>" in report  # sent as plain text, nothing to escape
    assert "_raise_deep" in report  # the useful end of the traceback is kept


def test_same_error_is_reported_once_per_window():
    now = [1000.0]
    throttle = ReportThrottle(window_seconds=600, clock=lambda: now[0])
    exc = RuntimeError("boom")
    assert throttle.should_send(exc, "кнопка 'a'")
    assert not throttle.should_send(exc, "кнопка 'a'")
    assert throttle.should_send(exc, "кнопка 'b'")
    now[0] += 601
    assert throttle.should_send(exc, "кнопка 'a'")


def test_config_warns_when_extra_ids_would_be_ignored(tmp_path):
    config = replace(make_config(tmp_path), allowed_user_ids={5, 111, 222}, admin_user_ids={5})
    warnings = config.runtime_warnings()
    assert any("players are [5, 111]" in w for w in warnings)


def test_config_warns_about_admin_without_access(tmp_path):
    config = replace(make_single_account_config(tmp_path), admin_user_ids={111, 999})
    assert any("[999]" in w for w in config.runtime_warnings())


def test_normal_config_has_no_warnings(tmp_path):
    assert make_config(tmp_path).runtime_warnings() == []
    assert make_single_account_config(tmp_path).runtime_warnings() == []


def test_scheduled_backup_copies_and_prunes_old_files(tmp_path):
    source = tmp_path / "bot.sqlite3"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES ('keep me')")
    backups = tmp_path / "backups"
    backups.mkdir()
    old = backups / "daily-20000101T000000Z.sqlite3"
    old.write_bytes(b"old")
    month_ago = time.time() - 30 * 86400
    os.utime(old, (month_ago, month_ago))
    deploy_backup = backups / "bot-20000101T000000Z-abc.sqlite3"
    deploy_backup.write_bytes(b"deploy")

    target = make_backup(source, backups, keep_days=14, now=datetime(2026, 10, 14, tzinfo=UTC))

    assert target.name == "daily-20261014T000000Z.sqlite3"
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT v FROM t").fetchone()[0] == "keep me"
    assert not old.exists()
    assert deploy_backup.exists()  # deploy backups are managed by deploy_server.sh


def test_scheduled_backup_never_deletes_the_only_backup(tmp_path):
    source = tmp_path / "bot.sqlite3"
    sqlite3.connect(source).close()
    backups = tmp_path / "backups"
    target = make_backup(source, backups, keep_days=0)
    assert target.exists()
