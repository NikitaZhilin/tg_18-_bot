from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable


CATEGORIES = {"question", "task", "pose", "desire", "penalty"}
INTENSITIES = {"light", "medium", "hard"}
INTENSITY_ORDER = {"light": 1, "medium": 2, "hard": 3}

FORBIDDEN_RISK_TAGS = {
    "minor_or_age_ambiguous",
    "non_consent",
    "coercion",
    "blackmail",
    "incapacitated_partner",
    "breath_control",
    "choking",
    "suffocation",
    "injury",
    "blood",
    "cutting",
    "needles",
    "weapon",
    "intoxication",
    "drug_use",
    "no_quick_release_restraint",
    "neck_restraint",
    "circulation_risk",
    "non_consent_roleplay_without_opt_in",
    "medical_risk",
    "unsafe_wax",
    "fire",
    "electric_shock",
    "public_nonconsenting_people",
    "recording_without_consent",
    "sharing_private_media",
    "non_human_participant",
    "self_harm",
    "unbounded_humiliation",
    "irreversible_marks",
}


@dataclass(frozen=True)
class PickFilter:
    session_id: int
    level: int | None = None
    category: str | None = None
    intensity: str | None = None
    allow_level_4: bool = False
    max_intensity: str = "light"


@dataclass(frozen=True)
class PickedCard:
    id: int
    external_id: str | None
    level: int
    category: str
    intensity: str
    title: str | None
    text: str
    timer_seconds: int | None
    safety_level: str
    risk_tags: tuple[str, ...]
    aftercare_required: bool


def parse_json_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value).strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def dump_json_list(values: Iterable[str]) -> str:
    clean = [str(value).strip() for value in values if str(value).strip()]
    return json.dumps(clean, ensure_ascii=False)


def bool_to_int(value: bool) -> int:
    return 1 if value else 0


def int_to_bool(value: object) -> bool:
    return bool(int(value or 0))


def intensity_allowed(card_intensity: str, max_intensity: str) -> bool:
    return INTENSITY_ORDER[card_intensity] <= INTENSITY_ORDER[max_intensity]
