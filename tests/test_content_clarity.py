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
