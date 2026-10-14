"""Daily SQLite backup with retention. Run by the tg-18-bot-backup systemd timer."""
from __future__ import annotations

import argparse
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

PREFIX = "daily-"


def make_backup(source: Path, backup_dir: Path, keep_days: int, now: datetime | None = None) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise SystemExit(f"database not found: {source}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"{PREFIX}{stamp}.sqlite3"
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_db, sqlite3.connect(target) as target_db:
        source_db.backup(target_db)
        integrity = target_db.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        target.unlink(missing_ok=True)
        raise SystemExit("backup integrity check failed")

    cutoff = time.time() - keep_days * 86400
    daily = sorted(backup_dir.glob(f"{PREFIX}*.sqlite3"))
    for old in daily[:-1]:  # never delete the newest backup
        if old.stat().st_mtime < cutoff:
            old.unlink(missing_ok=True)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("backup_dir")
    parser.add_argument("--keep-days", type=int, default=14)
    args = parser.parse_args()
    print(make_backup(Path(args.database), Path(args.backup_dir), args.keep_days))


if __name__ == "__main__":
    main()
