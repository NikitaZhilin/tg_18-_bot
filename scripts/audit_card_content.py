from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path


CONTENT_FILES = (
    Path("content/cards.csv"),
    Path("content/restricted_cards.csv"),
)

CATEGORY_MARKERS = {
    "question": ("Контекст:", "Ответьте:", "Итог:"),
    "task": ("Контекст:", "Порядок:", "Завершение:"),
    "pose": (
        "Исходное положение:",
        "Назначение:",
        "Действие:",
        "Завершение:",
    ),
    "desire": ("Контекст:", "Сейчас:", "Использование:", "Завершение:"),
    "penalty": ("Контекст:", "Выполнение:", "Завершение:"),
}

FORBIDDEN_PHRASES = (
    "из блока «контекст»",
    "выберите точную последовательность",
    "выберите одну основу",
    "названное действие",
    "названную последовательность",
    "соответствующее действие",
    "согласованное действие",
    "следующая выпавшая",
    "следующих карточек",
    "будущая карточка",
    "будущих карточек",
    "необходимый опыт",
    "самостоятельный ход",
    "из раздела «порядок»",
    "в разделе «порядок»",
    "из раздела «выполнение»",
)

ACTIVITY_MARKERS = (
    "поцелу",
    "объят",
    "массаж",
    "глад",
    "касани",
    "прикоснов",
    "ручн",
    "оральн",
    "куннилингус",
    "вульв",
    "клитор",
    "пенис",
    "вагинальн",
    "влагалищ",
    "анальн",
    "генитали",
    "проникнов",
    "команд",
    "один шаг",
    "взгляд",
)

DURATION_MARKERS = {
    "30": ("30 секунд", "полминут"),
    "60": ("60 секунд", "одну минут", "одна минут", "минутн"),
    "90": ("90 секунд", "полторы минут"),
    "120": ("120 секунд", "две минут", "двухминут"),
    "180": ("180 секунд", "три минут", "трехминут", "трёхминут"),
    "240": ("240 секунд", "четыре минут"),
    "300": ("300 секунд", "пять минут", "пятиминут"),
}


def load_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in CONTENT_FILES:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            rows.extend(csv.DictReader(source))
    return rows


def section(text: str, marker: str) -> str:
    pattern = rf"(?:^|\n\n){re.escape(marker)}\s*(.*?)(?=\n\n\S+?:|\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def audit(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    failures: dict[str, list[str]] = {
        "structure": [],
        "vague_phrases": [],
        "timer": [],
        "pose_action": [],
        "duplicates": [],
    }

    for row in rows:
        external_id = row["external_id"]
        text = row["text"].strip()
        category = row["category"]
        lowered = text.casefold()

        missing = [
            marker
            for marker in CATEGORY_MARKERS[category]
            if text.count(marker) != 1
        ]
        if not row["title"].strip() or len(text) < 80 or missing:
            failures["structure"].append(
                f"{external_id}: title={bool(row['title'].strip())}, "
                f"length={len(text)}, markers={missing}"
            )

        matches = [
            phrase for phrase in FORBIDDEN_PHRASES if phrase in lowered
        ]
        if matches:
            failures["vague_phrases"].append(
                f"{external_id}: {', '.join(matches)}"
            )

        timer = row.get("timer_seconds", "").strip()
        if timer:
            duration_is_named = any(
                marker in lowered for marker in DURATION_MARKERS.get(timer, ())
            )
            if "таймер" not in lowered and not duration_is_named:
                failures["timer"].append(
                    f"{external_id}: таймер {timer} сек. не объяснен в тексте"
                )
        elif "таймер" in lowered:
            failures["timer"].append(
                f"{external_id}: в тексте есть таймер, но timer_seconds пуст"
            )

        if category == "pose":
            purpose = section(text, "Назначение:").casefold()
            action = section(text, "Действие:").casefold()
            purpose_activities = {
                marker for marker in ACTIVITY_MARKERS if marker in purpose
            }
            action_activities = {
                marker for marker in ACTIVITY_MARKERS if marker in action
            }
            if purpose_activities and not purpose_activities & action_activities:
                failures["pose_action"].append(
                    f"{external_id}: действие не повторяет назначение"
                )

    for field in ("title", "text"):
        counts = Counter(
            row[field].strip().casefold()
            for row in rows
            if row[field].strip()
        )
        duplicates = [value for value, count in counts.items() if count > 1]
        for value in duplicates:
            ids = [
                row["external_id"]
                for row in rows
                if row[field].strip().casefold() == value
            ]
            failures["duplicates"].append(f"{field}: {', '.join(ids)}")

    return failures


def main() -> None:
    rows = load_rows()
    failures = audit(rows)
    print(f"Проверено карточек: {len(rows)}")
    total = 0
    for name, entries in failures.items():
        print(f"{name}: {len(entries)}")
        for entry in entries:
            print(f"  - {entry}")
        total += len(entries)
    if total:
        raise SystemExit(1)
    print("Ошибок не найдено.")


if __name__ == "__main__":
    main()
