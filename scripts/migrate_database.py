from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config
from app.storage import Database


def main() -> None:
    config = Config.from_env()
    database = Database(config.database_path)
    try:
        database.apply_migrations()
    finally:
        database.close()
    print(f"migrations applied: {config.database_path.resolve()}")


if __name__ == "__main__":
    main()
