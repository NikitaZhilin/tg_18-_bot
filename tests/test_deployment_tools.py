from __future__ import annotations

import sqlite3
import subprocess
import sys
import time


def test_database_backup_restore_and_health_check(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE values_table (value TEXT NOT NULL)")
        connection.execute("INSERT INTO values_table VALUES ('original')")
        connection.execute(
            """
            CREATE TABLE app_heartbeats (
                component TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                details TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO app_heartbeats (component, status, details)
            VALUES ('polling_bot', 'ok', '{}')
            """
        )
        connection.commit()

    subprocess.run(
        [sys.executable, "scripts/backup_database.py", str(source), str(backup)],
        check=True,
    )
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE values_table SET value = 'changed'")
        connection.commit()
    subprocess.run(
        [sys.executable, "scripts/restore_database.py", str(backup), str(restored)],
        check=True,
    )
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM values_table").fetchone()[0] == "original"

    healthy = subprocess.run(
        [
            sys.executable,
            "scripts/health_check.py",
            str(restored),
            "--max-age",
            "60",
        ],
        capture_output=True,
        text=True,
    )
    assert healthy.returncode == 0, healthy.stderr

    stale_for_deployment = subprocess.run(
        [
            sys.executable,
            "scripts/health_check.py",
            str(restored),
            "--updated-after",
            str(time.time() + 60),
        ],
        capture_output=True,
        text=True,
    )
    assert stale_for_deployment.returncode != 0
