from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config
from app.main import build_services
from app.services.content_importer import ContentImporter


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DRY_RUN"] = "true"
        os.environ.setdefault("ALLOW_UNLISTED_USERS", "true")
        os.environ.setdefault("ALLOWED_TELEGRAM_USER_IDS", "111,222")
        os.environ["DATA_DIR"] = tmp
        os.environ["DATABASE_PATH"] = str(Path(tmp) / "bot.sqlite3")
        config = Config.from_env()
        db, _services = build_services(config)
        seed = Path("content/cards.csv")
        if seed.exists():
            report = ContentImporter(db).import_file(seed, dry_run=True)
            if report.warnings_count:
                raise SystemExit(f"seed warnings: {report.warnings_count}")
        db.close()
    print("smoke ok")


if __name__ == "__main__":
    main()
