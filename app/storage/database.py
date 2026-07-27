from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def in_memory(cls) -> "Database":
        return cls(":memory:")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def apply_migrations(self, migrations_dir: str | Path | None = None) -> None:
        base = Path(migrations_dir) if migrations_dir else Path(__file__).parent / "migrations"
        for migration in sorted(base.glob("*.sql")):
            sql = migration.read_text(encoding="utf-8")
            with self._lock:
                self._conn.executescript(sql)
                self._conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                yield self._conn
            except Exception:
                self._conn.rollback()
                raise
            else:
                self._conn.commit()

    def execute(self, sql: str, params: Sequence[object] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def executemany(self, sql: str, params: Sequence[Sequence[object]]) -> None:
        with self._lock:
            self._conn.executemany(sql, params)
            self._conn.commit()

    def fetchone(self, sql: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())
