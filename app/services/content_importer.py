from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain import CATEGORIES, FORBIDDEN_RISK_TAGS, INTENSITIES, dump_json_list, parse_json_list
from app.labels import ITEM_MODE_NAMES
from app.services.content_readers import read_csv, read_docx, read_xlsx
from app.storage import Database
from app.storage.repositories.admin_actions import AdminActionRepository
from app.storage.repositories.cards import CardRepository
from app.storage.repositories.items import ItemRepository


@dataclass
class ImportWarning:
    row_number: int
    external_id: str | None
    message: str


@dataclass
class ImportReport:
    source_file: str
    content_version: str
    added_or_updated: int = 0
    items_added_or_updated: int = 0
    disabled_cards: int = 0
    needs_review: int = 0
    conflicts: int = 0
    warnings: list[ImportWarning] = field(default_factory=list)
    dry_run: bool = False

    @property
    def warnings_count(self) -> int:
        return len(self.warnings)


class ContentImporter:
    def __init__(self, db: Database):
        self.db = db
        self.cards = CardRepository(db)
        self.items = ItemRepository(db)
        self.admin_actions = AdminActionRepository(db)

    def import_file(
        self,
        path: str | Path,
        *,
        content_version: str = "manual",
        dry_run: bool = False,
        admin_user_id: int | None = None,
        skip_existing: bool = False,
        preserve_admin_changes: bool = False,
        skip_imported_version: bool = False,
    ) -> ImportReport:
        path = Path(path)
        report = ImportReport(str(path), content_version, dry_run=dry_run)
        if skip_imported_version and self.db.fetchone(
            "SELECT 1 FROM content_imports WHERE content_version = ? LIMIT 1",
            (content_version,),
        ):
            return report

        item_rows: list[dict[str, Any]] = []
        if path.suffix.lower() == ".csv":
            rows = read_csv(path)
        elif path.suffix.lower() in {".xlsx", ".xlsm"}:
            rows, item_rows = read_xlsx(path)
        elif path.suffix.lower() == ".docx":
            rows = read_docx(path)
        else:
            raise ValueError(f"unsupported content file: {path.suffix}")

        prepared_rows: list[tuple[dict[str, Any], list[str], list[str]]] = []
        conflict_rows: list[tuple[int, dict[str, Any], list[str], list[str]]] = []
        trusted_seed = path.parent.resolve() == Path("content").resolve()
        existing_external_ids = {
            str(row["external_id"])
            for row in self.db.fetchall(
                "SELECT external_id FROM cards WHERE external_id IS NOT NULL"
            )
        }
        admin_modified_external_ids = {
            str(row["external_id"])
            for row in self.db.fetchall(
                """
                SELECT DISTINCT c.external_id
                FROM cards c
                JOIN card_versions cv ON cv.card_id = c.id
                WHERE c.external_id IS NOT NULL
                """
            )
        } if preserve_admin_changes else set()
        known_item_codes = {
            str(row["code"])
            for row in self.db.fetchall(
                "SELECT code FROM items WHERE deleted_at IS NULL"
            )
        }
        known_item_codes.update(
            str(item["code"])
            for item in item_rows
            if str(item.get("code") or "").strip()
        )

        for index, row in enumerate(rows, start=2):
            external_id = str(row.get("external_id") or "").strip()
            if skip_existing and external_id in existing_external_ids:
                continue
            if trusted_seed:
                row["_trusted_seed"] = "1"
            try:
                card_data, items, collections = self._prepare_row(row)
            except ValueError as exc:
                report.warnings.append(ImportWarning(index, row.get("external_id"), str(exc)))
                continue
            unknown_items = sorted(set(items) - known_item_codes)
            if unknown_items:
                report.warnings.append(
                    ImportWarning(
                        index,
                        card_data["external_id"],
                        "Неизвестный реквизит: " + ", ".join(unknown_items),
                    )
                )
                continue
            if card_data["review_status"] == "disabled":
                report.disabled_cards += 1
            if card_data["review_status"] == "needs_review":
                report.needs_review += 1
            if external_id in admin_modified_external_ids:
                existing = self.cards.get_by_external_id(external_id)
                if existing:
                    conflict_rows.append((int(existing["id"]), card_data, items, collections))
                    report.conflicts += 1
                continue
            prepared_rows.append((card_data, items, collections))

        report.added_or_updated = len(prepared_rows)
        report.items_added_or_updated = len(item_rows)
        if dry_run:
            return report

        with self.db.transaction() as conn:
            for item_data in item_rows:
                self.items.upsert_from_import(item_data, conn)
            for card_data, items, collections in prepared_rows:
                card_id = self.cards.upsert(card_data, items, collections, conn)
                self.cards.set_archived(card_id, bool(card_data.get("_is_archived")), conn)
            for card_id, card_data, items, collections in conflict_rows:
                incoming = {
                    "card": card_data,
                    "required_items": items,
                    "collections": collections,
                    "is_archived": bool(card_data.get("_is_archived")),
                }
                conn.execute(
                    """
                    INSERT INTO seed_conflicts (
                        card_id, external_id, source_file, content_version, incoming_json
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(card_id, content_version) DO NOTHING
                    """,
                    (
                        card_id,
                        str(card_data["external_id"]),
                        str(path),
                        content_version,
                        json.dumps(incoming, ensure_ascii=False),
                    ),
                )
            conn.execute(
                """
                INSERT INTO content_imports (
                    source_file, content_version, imported_cards, disabled_cards, warnings_count, report_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(path),
                    content_version,
                    report.added_or_updated,
                    report.disabled_cards,
                    report.warnings_count,
                    json.dumps({"conflicts": report.conflicts}, ensure_ascii=False),
                ),
            )
        if admin_user_id:
            self.admin_actions.record(
                admin_user_id,
                "import_cards",
                "content_file",
                str(path),
                {
                    "content_version": content_version,
                    "imported_cards": report.added_or_updated,
                    "disabled_cards": report.disabled_cards,
                    "warnings_count": report.warnings_count,
                    "items_added_or_updated": report.items_added_or_updated,
                    "conflicts": report.conflicts,
                },
            )
        return report

    @staticmethod
    def _prepare_row(row: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
        external_id = str(row.get("external_id") or "").strip()
        if not external_id:
            raise ValueError("external_id is required")
        text = str(row.get("text") or "").strip()
        if not text:
            raise ValueError("text is required")
        level = int(str(row.get("level") or "1").strip())
        if level < 1 or level > 4:
            raise ValueError("level must be 1..4")
        category = str(row.get("category") or "task").strip()
        if category not in CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        intensity = str(row.get("intensity") or "light").strip()
        if intensity not in INTENSITIES:
            raise ValueError(f"unknown intensity: {intensity}")
        item_mode = str(row.get("item_mode") or "none").strip()
        if item_mode not in ITEM_MODE_NAMES:
            raise ValueError(f"unknown item mode: {item_mode}")

        risk_tags = set(parse_json_list(row.get("risk_tags")))
        avoid_if_tags = parse_json_list(row.get("avoid_if_tags"))
        forbidden = risk_tags.intersection(FORBIDDEN_RISK_TAGS)
        review_status = str(row.get("review_status") or "draft").strip()
        is_enabled = _to_bool(row.get("is_enabled"), default=False)
        aftercare_required = _to_bool(row.get("aftercare_required"), default=False)

        if level == 4 or intensity == "hard":
            aftercare_required = True
            if _to_bool(row.get("_trusted_seed")) and review_status == "needs_review":
                review_status = "approved"
                is_enabled = True
        if forbidden:
            is_enabled = False
            review_status = "disabled"
        elif review_status != "approved":
            is_enabled = False

        if category == "pose":
            for field_name in ("pose_family", "pose_difficulty", "space_required", "body_load"):
                if not str(row.get(field_name) or "").strip():
                    raise ValueError(f"{field_name} is required for pose")

        timer_seconds = str(row.get("timer_seconds") or "").strip()
        card_data = {
            "external_id": external_id,
            "level": level,
            "category": category,
            "intensity": intensity,
            "title": _empty_to_none(row.get("title")),
            "text": text,
            "media_id": _empty_to_none(row.get("media_id")),
            "media_file": _empty_to_none(row.get("media_file")),
            "media_type": _empty_to_none(row.get("media_type")),
            "pose_family": _empty_to_none(row.get("pose_family")),
            "pose_difficulty": _empty_to_none(row.get("pose_difficulty")),
            "space_required": _empty_to_none(row.get("space_required")),
            "body_load": _empty_to_none(row.get("body_load")),
            "avoid_if_tags": dump_json_list(avoid_if_tags),
            "source_note": _empty_to_none(row.get("source_note")),
            "timer_seconds": int(timer_seconds) if timer_seconds else None,
            "risk_tags": dump_json_list(risk_tags),
            "aftercare_required": 1 if aftercare_required else 0,
            "item_mode": item_mode,
            "is_enabled": 1 if is_enabled else 0,
            "review_status": review_status,
            "notes": _empty_to_none(row.get("notes")),
            "_is_archived": 1 if _to_bool(row.get("_is_archived")) else 0,
        }
        items = parse_json_list(row.get("required_items"))
        if items and item_mode != "required":
            raise ValueError(
                "При явно указанном реквизите выберите режим «Обязательно подобрать»"
            )
        collections = parse_json_list(row.get("collections") or row.get("collection"))
        if not collections:
            collections = ["base_tasks"]
        return card_data, items, collections


def _empty_to_none(value: object) -> str | None:
    raw = str(value or "").strip()
    return raw or None


def _to_bool(value: object, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "да"}
