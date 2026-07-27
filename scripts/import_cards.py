from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config
from app.services.content_importer import ContentImporter
from app.storage import Database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--check", action="store_true", help="Validate without writing to DB")
    parser.add_argument("--content-version", default="manual")
    args = parser.parse_args()

    config = Config.from_env()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(config.database_path)
    db.apply_migrations()
    report = ContentImporter(db).import_file(
        args.path,
        content_version=args.content_version,
        dry_run=args.check,
    )
    db.close()
    print(f"source: {report.source_file}")
    print(f"dry_run: {report.dry_run}")
    print(f"added_or_updated: {report.added_or_updated}")
    print(f"disabled_cards: {report.disabled_cards}")
    print(f"needs_review: {report.needs_review}")
    print(f"warnings: {report.warnings_count}")
    for warning in report.warnings[:20]:
        print(f"row {warning.row_number} {warning.external_id or ''}: {warning.message}")
    if report.warnings_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
