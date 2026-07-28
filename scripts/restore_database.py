from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    parser.add_argument("target")
    args = parser.parse_args()

    backup = Path(args.backup).resolve()
    target = Path(args.target).resolve()
    if not backup.is_file():
        raise SystemExit(f"backup not found: {backup}")
    with sqlite3.connect(f"file:{backup}?mode=ro", uri=True) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        raise SystemExit("backup integrity check failed")

    target.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{target}-wal").unlink(missing_ok=True)
    Path(f"{target}-shm").unlink(missing_ok=True)
    shutil.copy2(backup, target)
    print(target)


if __name__ == "__main__":
    main()
