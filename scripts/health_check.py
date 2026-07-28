from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def parse_timestamp(raw: str) -> datetime:
    value = raw.strip().replace(" ", "T")
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("--component", default="polling_bot")
    parser.add_argument("--max-age", type=int, default=90)
    parser.add_argument("--updated-after", type=float, default=0)
    args = parser.parse_args()

    database = Path(args.database).resolve()
    if not database.is_file():
        raise SystemExit(f"database not found: {database}")
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute(
            """
            SELECT status, updated_at
            FROM app_heartbeats
            WHERE component = ?
            """,
            (args.component,),
        ).fetchone()
    if not row:
        raise SystemExit("heartbeat not found")
    updated_at = parse_timestamp(str(row[1]))
    age = (datetime.now(UTC) - updated_at).total_seconds()
    if row[0] != "ok":
        raise SystemExit(f"heartbeat status is {row[0]}")
    if updated_at.timestamp() < args.updated_after:
        raise SystemExit("heartbeat predates current deployment")
    if age > args.max_age:
        raise SystemExit(f"heartbeat is stale: {age:.1f}s")
    print(f"health ok: {args.component}, age={age:.1f}s")


if __name__ == "__main__":
    main()
