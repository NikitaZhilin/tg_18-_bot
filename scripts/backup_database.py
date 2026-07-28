from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    if not source.is_file():
        raise SystemExit(f"database not found: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
        source_db.backup(target_db)
        integrity = target_db.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        target.unlink(missing_ok=True)
        raise SystemExit("backup integrity check failed")
    print(target)


if __name__ == "__main__":
    main()
