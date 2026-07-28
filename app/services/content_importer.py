from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain import CATEGORIES, FORBIDDEN_RISK_TAGS, INTENSITIES, dump_json_list, parse_json_list
from app.storage import Database
from app.storage.repositories.admin_actions import AdminActionRepository
from app.storage.repositories.cards import CardRepository


REQUIRED_COLUMNS = {"external_id", "level", "category", "text"}
RISK_KEYWORDS = {
    "breath_control": ("дыхани", "удуш", "перекры"),
    "choking": ("горло", "шею", "шея"),
    "unsafe_wax": ("воск", "свеч"),
    "no_quick_release_restraint": ("свяж", "связ", "верев"),
    "unbounded_humiliation": ("униж",),
    "intoxication": ("алког", "опьян"),
    "recording_without_consent": ("фото", "видео", "запиш"),
    "public_nonconsenting_people": ("публич", "посторон"),
    "injury": ("боль", "удар", "след", "синяк"),
}
ITEM_ALIASES = {
    "лед": "ice",
    "масло": "oil",
    "веревка": "rope",
    "верёвка": "rope",
    "повязка": "blindfold",
    "вибратор": "vibrator",
    "наушники": "headphones",
    "свеча": "candle",
    "свечи": "candle",
    "зажимы": "clamps",
    "еда": "food",
}


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
    disabled_cards: int = 0
    needs_review: int = 0
    warnings: list[ImportWarning] = field(default_factory=list)
    dry_run: bool = False

    @property
    def warnings_count(self) -> int:
        return len(self.warnings)


class ContentImporter:
    def __init__(self, db: Database):
        self.db = db
        self.cards = CardRepository(db)
        self.admin_actions = AdminActionRepository(db)

    def import_file(
        self,
        path: str | Path,
        *,
        content_version: str = "manual",
        dry_run: bool = False,
        admin_user_id: int | None = None,
    ) -> ImportReport:
        path = Path(path)
        if path.suffix.lower() == ".csv":
            rows = self._read_csv(path)
        elif path.suffix.lower() in {".xlsx", ".xlsm"}:
            rows = self._read_xlsx(path)
        elif path.suffix.lower() == ".docx":
            rows = self._read_docx(path)
        else:
            raise ValueError(f"unsupported content file: {path.suffix}")

        report = ImportReport(str(path), content_version, dry_run=dry_run)
        prepared_rows: list[tuple[dict[str, Any], list[str], list[str]]] = []
        trusted_seed = path.parent.resolve() == Path("content").resolve()

        for index, row in enumerate(rows, start=2):
            if trusted_seed:
                row["_trusted_seed"] = "1"
            try:
                card_data, items, collections = self._prepare_row(row)
            except ValueError as exc:
                report.warnings.append(ImportWarning(index, row.get("external_id"), str(exc)))
                continue
            if card_data["review_status"] == "disabled":
                report.disabled_cards += 1
            if card_data["review_status"] == "needs_review":
                report.needs_review += 1
            prepared_rows.append((card_data, items, collections))

        report.added_or_updated = len(prepared_rows)
        if dry_run:
            return report

        with self.db.transaction() as conn:
            for card_data, items, collections in prepared_rows:
                self.cards.upsert(card_data, items, collections, conn)
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
                    "{}",
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
                },
            )
        return report

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
                missing = ", ".join(sorted(REQUIRED_COLUMNS - set(reader.fieldnames or [])))
                raise ValueError(f"missing required columns: {missing}")
            return [dict(row) for row in reader]

    @staticmethod
    def _read_xlsx(path: Path) -> list[dict[str, str]]:
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(cell or "").strip() for cell in rows[0]]
        if not REQUIRED_COLUMNS.issubset(set(headers)):
            missing = ", ".join(sorted(REQUIRED_COLUMNS - set(headers)))
            raise ValueError(f"missing required columns: {missing}")
        result = []
        for raw in rows[1:]:
            result.append({headers[i]: "" if raw[i] is None else str(raw[i]) for i in range(len(headers))})
        return result

    @staticmethod
    def _read_docx(path: Path) -> list[dict[str, str]]:
        from docx import Document

        doc = Document(path)
        rows: list[dict[str, str]] = []
        level = 1
        counter = 1
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            lower = text.lower()
            if "уровень 1" in lower:
                level = 1
                continue
            if "уровень 2" in lower:
                level = 2
                continue
            if "уровень 3" in lower:
                level = 3
                continue
            if "уровень 4" in lower:
                level = 4
                continue
            if len(text) < 12:
                continue
            required_items = _extract_items(text)
            timer_seconds = _extract_timer_seconds(text)
            risk_tags = _detect_risk_tags(text)
            rows.append(
                {
                    "external_id": f"docx_l{level}_{counter:03d}",
                    "level": str(level),
                    "category": "task",
                    "intensity": "light" if level < 3 else "medium",
                    "title": "",
                    "text": _strip_docx_metadata(text),
                    "required_items": ",".join(required_items),
                    "timer_seconds": str(timer_seconds or ""),
                    "risk_tags": ",".join(risk_tags),
                    "collection": "base_tasks",
                    "review_status": "needs_review",
                    "is_enabled": "0",
                }
            )
            counter += 1
        return rows

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

        risk_tags = set(parse_json_list(row.get("risk_tags")))
        avoid_if_tags = parse_json_list(row.get("avoid_if_tags"))
        forbidden = risk_tags.intersection(FORBIDDEN_RISK_TAGS)
        review_status = str(row.get("review_status") or "draft").strip()
        is_enabled = _to_bool(row.get("is_enabled"), default=False)
        requires_both_opt_in = _to_bool(row.get("requires_both_opt_in"), default=False)
        requires_safeword_check = _to_bool(row.get("requires_safeword_check"), default=False)
        aftercare_required = _to_bool(row.get("aftercare_required"), default=False)

        if level == 4 or intensity == "hard":
            requires_both_opt_in = True
            requires_safeword_check = True
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
            "safety_level": str(row.get("safety_level") or "normal").strip(),
            "risk_tags": dump_json_list(risk_tags),
            "requires_both_opt_in": 1 if requires_both_opt_in else 0,
            "requires_safeword_check": 1 if requires_safeword_check else 0,
            "aftercare_required": 1 if aftercare_required else 0,
            "is_enabled": 1 if is_enabled else 0,
            "review_status": review_status,
            "notes": _empty_to_none(row.get("notes")),
        }
        items = parse_json_list(row.get("required_items"))
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


def _extract_items(text: str) -> list[str]:
    match = re.search(r"\[?\s*Реквизит\s*:\s*([^\]\n]+)\]?", text, flags=re.IGNORECASE)
    if not match:
        return []
    raw_value = re.split(r"\bТаймер\s*:", match.group(1), flags=re.IGNORECASE)[0]
    raw_items = parse_json_list(raw_value)
    result = []
    for raw in raw_items:
        key = raw.lower().strip()
        result.append(ITEM_ALIASES.get(key, key))
    return result


def _extract_timer_seconds(text: str) -> int | None:
    match = re.search(r"\[?\s*Таймер\s*:\s*(\d+)\s*(сек|секунд|мин|минут)?", text, flags=re.IGNORECASE)
    if not match:
        return None
    value = int(match.group(1))
    unit = (match.group(2) or "сек").lower()
    return value * 60 if unit.startswith("мин") else value


def _detect_risk_tags(text: str) -> list[str]:
    lower = text.lower()
    detected = []
    for tag, keywords in RISK_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            detected.append(tag)
    return detected


def _strip_docx_metadata(text: str) -> str:
    text = re.sub(r"\[?\s*Реквизит\s*:\s*[^\]\n]+\]?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[?\s*Таймер\s*:\s*[^\]\n]+\]?", "", text, flags=re.IGNORECASE)
    return " ".join(text.split())
