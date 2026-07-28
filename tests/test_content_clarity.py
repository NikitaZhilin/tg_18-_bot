from __future__ import annotations

import csv
from pathlib import Path


def _content_rows():
    rows = []
    for path in (Path("content/cards.csv"), Path("content/restricted_cards.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            rows.extend(csv.DictReader(source))
    return rows


def test_content_has_no_internal_english_or_numbered_placeholders():
    forbidden_fragments = {
        "check-in",
        "aftercare",
        "safeword-check",
        "stop-check",
        "risk-tag",
        " light ",
        " medium ",
        " hard ",
        "желание номер",
        "вопрос о желании, границе или настроении вечера номер",
        "игровой штраф номер",
    }
    failures = []
    for row in _content_rows():
        normalized = f" {row['text'].casefold()} "
        for fragment in forbidden_fragments:
            if fragment in normalized:
                failures.append((row["external_id"], fragment))
    assert failures == []


def test_cards_that_ask_for_random_item_have_explicit_item_mode():
    failures = []
    for row in _content_rows():
        text = row["text"].casefold()
        asks_for_item = "реквизит, который указал бот" in text
        if asks_for_item and row["item_mode"] != "required":
            failures.append(row["external_id"])
    assert failures == []


def test_cards_with_explicit_items_mark_them_as_required():
    failures = [
        row["external_id"]
        for row in _content_rows()
        if row["required_items"] and row["item_mode"] != "required"
    ]
    assert failures == []


def test_internal_level_and_intensity_codes_are_not_used_as_titles():
    failures = []
    for row in _content_rows():
        title = row.get("title", "").casefold()
        if title.startswith("уровень ") or any(
            token in f" {title} " for token in (" light ", " medium ", " hard ")
        ):
            failures.append((row["external_id"], row["title"]))
    assert failures == []


def test_extreme_sheet_content_is_consistently_gated():
    with Path("content/restricted_cards.csv").open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 18
    for row in rows:
        assert row["level"] == "4"
        assert row["intensity"] == "hard"
        assert row["collection"] == "restricted_content"
        assert row["requires_both_opt_in"] == "1"
        assert row["requires_safeword_check"] == "1"
        assert row["aftercare_required"] == "1"


def test_extreme_cards_have_titles_and_actionable_structure():
    with Path("content/restricted_cards.csv").open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source:
        rows = list(csv.DictReader(source))

    required_markers = {
        "question": ("ответьте", "завершение:"),
        "task": ("до начала:", "действие:", "завершение:"),
        "pose": ("исходное положение:", "действие:", "завершение:"),
        "desire": ("сейчас:", "использование:", "завершение:"),
    }
    failures = []
    for row in rows:
        text = row["text"].casefold()
        missing = [marker for marker in required_markers[row["category"]] if marker not in text]
        if not row["title"].strip() or missing:
            failures.append((row["external_id"], row["title"], missing))

    assert failures == []


def test_all_builtin_cards_have_clear_titles_and_substantial_text():
    failures = []
    for row in _content_rows():
        if not row["title"].strip():
            failures.append((row["external_id"], "нет названия"))
        if len(row["text"].strip()) < 80:
            failures.append((row["external_id"], "текст короче 80 символов"))
    assert failures == []


def test_all_poses_and_desires_explain_the_complete_flow():
    failures = []
    for row in _content_rows():
        text = row["text"].casefold()
        if row["category"] == "pose":
            markers = ("исходное положение:", "действие:", "завершение:")
        elif row["category"] == "desire":
            markers = ("сейчас:", "использование:", "завершение:")
        else:
            continue
        missing = [marker for marker in markers if marker not in text]
        if missing:
            failures.append((row["external_id"], missing))
    assert failures == []


def test_game_cards_do_not_send_players_into_admin_tools():
    forbidden = (
        "администратор",
        "откройте «границы",
        "открыть «границы",
        "каталог карточек",
        "без отдельного названия",
        "в согласованных пределах",
        "обязателен проверка",
        "обязателен спокойное",
    )
    failures = []
    for row in _content_rows():
        text = row["text"].casefold()
        matches = [fragment for fragment in forbidden if fragment in text]
        if matches:
            failures.append((row["external_id"], matches))
    assert failures == []


def test_optional_item_cards_explicitly_explain_random_prop():
    failures = []
    for row in _content_rows():
        if row["item_mode"] == "optional" and "если бот указал реквизит" not in row["text"].casefold():
            failures.append(row["external_id"])
    assert failures == []


def test_builtin_titles_and_texts_are_not_duplicated():
    rows = _content_rows()
    for field in ("title", "text"):
        grouped = {}
        for row in rows:
            grouped.setdefault(row[field].strip().casefold(), []).append(row["external_id"])
        duplicates = [ids for value, ids in grouped.items() if value and len(ids) > 1]
        assert duplicates == []


def test_explicit_card_durations_match_telegram_timers():
    expected_timers = {
        "task_l1_015": "60",
        "task_l2_012": "120",
        "task_l2_016": "60",
        "task_l3_light_006": "60",
        "task_l3_medium_006": "60",
        "task_l4_light_001": "120",
        "task_l4_medium_006": "60",
        "task_l4_hard_009": "60",
        "pose_ks_012": "30",
        "pose_ks_016": "90",
        "pose_ks_017": "90",
        "pose_ks_020": "60",
        "pose_ks_024": "90",
    }
    actual = {
        row["external_id"]: row["timer_seconds"]
        for row in _content_rows()
        if row["external_id"] in expected_timers
    }
    assert actual == expected_timers
