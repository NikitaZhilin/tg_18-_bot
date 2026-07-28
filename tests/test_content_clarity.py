from __future__ import annotations

import csv
import re
from pathlib import Path


def _content_rows():
    rows = []
    for path in (Path("content/cards.csv"), Path("content/restricted_cards.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            rows.extend(csv.DictReader(source))
    return rows


def test_all_cards_pass_full_content_audit():
    from scripts.audit_card_content import audit

    failures = audit(_content_rows())
    assert {name: entries for name, entries in failures.items() if entries} == {}


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
    assert len(rows) == 22
    for row in rows:
        assert row["level"] == "4"
        assert row["intensity"] == "hard"
        assert row["collection"] == "restricted_content"
        assert row["requires_both_opt_in"] == "1"
        assert row["requires_safeword_check"] == "1"
        assert row["aftercare_required"] == "1"

    active = [row for row in rows if row["review_status"] == "approved"]
    drafts = [row for row in rows if row["review_status"] == "draft"]
    assert len(active) == 19
    assert all(row["is_enabled"] == "1" for row in active)
    assert {
        row["external_id"] for row in drafts
    } == {
        "restricted_l4_hard_fisting_progression_draft",
        "restricted_l4_hard_urethral_progression_draft",
        "restricted_l4_hard_rope_restraint_draft",
    }
    assert all(row["is_enabled"] == "0" for row in drafts)


def test_extreme_cards_have_titles_and_actionable_structure():
    with Path("content/restricted_cards.csv").open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source:
        rows = list(csv.DictReader(source))

    required_markers = {
        "question": ("контекст:", "ответьте:", "итог:"),
        "task": ("контекст:", "порядок:", "завершение:"),
        "pose": ("исходное положение:", "назначение:", "действие:", "завершение:"),
        "desire": ("контекст:", "сейчас:", "использование:", "завершение:"),
    }
    failures = []
    for row in rows:
        text = row["text"].casefold()
        missing = [marker for marker in required_markers[row["category"]] if marker not in text]
        if not row["title"].strip() or missing:
            failures.append((row["external_id"], row["title"], missing))

    assert failures == []


def test_every_card_has_one_complete_category_specific_structure():
    required_markers = {
        "question": ("Контекст:", "Ответьте:", "Итог:"),
        "task": ("Контекст:", "Порядок:", "Завершение:"),
        "pose": ("Исходное положение:", "Назначение:", "Действие:", "Завершение:"),
        "desire": ("Контекст:", "Сейчас:", "Использование:", "Завершение:"),
        "penalty": ("Контекст:", "Выполнение:", "Завершение:"),
    }
    failures = []
    for row in _content_rows():
        text = row["text"]
        for marker in required_markers[row["category"]]:
            count = text.count(marker)
            if count != 1:
                failures.append((row["external_id"], marker, count))
    assert failures == []


def test_user_editable_placeholders_are_disabled_restricted_drafts_only():
    placeholder = "Пользователь исправит самостоятельно"
    rows = [row for row in _content_rows() if placeholder in row["text"]]
    assert {
        row["external_id"] for row in rows
    } == {
        "restricted_l4_hard_fisting_progression_draft",
        "restricted_l4_hard_urethral_progression_draft",
        "restricted_l4_hard_rope_restraint_draft",
    }
    for row in rows:
        assert row["collection"] == "restricted_content"
        assert row["review_status"] == "draft"
        assert row["is_enabled"] == "0"


def test_active_cards_never_show_internal_placeholders():
    failures = [
        row["external_id"]
        for row in _content_rows()
        if row["is_enabled"] == "1"
        and "пользователь исправит самостоятельно" in row["text"].casefold()
    ]
    assert failures == []


def test_active_sex_and_bdsm_tasks_name_a_concrete_activity_or_explicitly_start_none():
    concrete_fragments = (
        "целу",
        "куннилингус",
        "оральн",
        "ручн",
        "вагинальн",
        "анальн",
        "влагалищ",
        "ласка",
        "массаж",
        "реквизит",
        "прикоснов",
        "команд",
        "положен",
        "один шаг",
        "шаг ближе",
        "фистинг",
        "не запуска",
        "не начина",
        "не выполня",
        "провер",
        "восстанов",
        "нет интимных действий",
    )
    failures = []
    for row in _content_rows():
        if row["category"] != "task" or int(row["level"]) < 3:
            continue
        if row["review_status"] == "draft":
            continue
        text = row["text"].casefold()
        if not any(fragment in text for fragment in concrete_fragments):
            failures.append(row["external_id"])
    assert failures == []


def test_pose_starting_positions_do_not_use_open_ended_placeholders():
    forbidden = (
        "выберите одну устойчивую позу",
        "выбирает удобную позу",
        "ложится или садится удобно",
        "располагается сверху или сбоку",
        "располагается перед ним или сбоку",
    )
    failures = []
    for row in _content_rows():
        if row["category"] != "pose":
            continue
        text = row["text"].casefold()
        matches = [fragment for fragment in forbidden if fragment in text]
        if matches:
            failures.append((row["external_id"], matches))
    assert failures == []


def test_previously_reported_contextless_phrases_do_not_return():
    forbidden = (
        "перед каждым новым действием",
        "во время этой карточки любой партнер может",
        "после сигнала таймера полностью остановитесь. каждый заканчивает",
        "выберите одно место: кровать",
        "короткую команду, которую хотел бы услышать",
        "необходимый опыт",
        "выполните согласованное действие",
        "использует только заранее согласованные команды",
        "новое действие из заранее разрешенного списка",
        "выберите одну удобную позу",
        "выберите удобную позу",
        "названное действие",
        "после указанного действия",
        "последнего указанного ответа или проверки",
        "самостоятельный ход",
        "самостоятельный игровой штраф",
        "что нужно убрать из следующих ходов",
        "как он должен проявляться в следующих ходах",
    )
    failures = []
    for row in _content_rows():
        text = row["text"].casefold()
        matches = [fragment for fragment in forbidden if fragment in text]
        if matches:
            failures.append((row["external_id"], matches))
    assert failures == []


def test_game_cards_do_not_use_unexplained_turn_jargon():
    failures = []
    turn_word = re.compile(r"\bход(?:а|ов|е|ом|ы|ах)?\b", re.IGNORECASE)
    for row in _content_rows():
        matches = turn_word.findall(f"{row['title']} {row['text']}")
        if matches:
            failures.append((row["external_id"], matches))
    assert failures == []


def test_task_context_and_order_do_not_switch_intimate_activity_implicitly():
    activity_markers = {
        "vaginal": ("вагинальн", "влагалищ"),
        "anal": ("анальн",),
        "oral_penis": ("оральн", "пенис"),
        "cunnilingus": ("куннилингус", "вульв", "клитор"),
        "fisting": ("фистинг",),
    }
    failures = []
    for row in _content_rows():
        if row["category"] != "task" or int(row["level"]) < 3:
            continue
        paragraphs = row["text"].casefold().split("\n\n")
        context = paragraphs[0]
        order = next(
            (part for part in paragraphs if part.startswith("порядок:")),
            "",
        )
        if "из порядка ниже" in context:
            continue

        def activities(section):
            found = set()
            for name, markers in activity_markers.items():
                if name == "oral_penis":
                    if "оральн" in section and "пенис" in section:
                        found.add(name)
                elif any(marker in section for marker in markers):
                    found.add(name)
            return found

        context_activities = activities(context)
        order_activities = activities(order)
        unexpected = order_activities - context_activities
        if context_activities and unexpected:
            failures.append(
                (
                    row["external_id"],
                    sorted(context_activities),
                    sorted(unexpected),
                )
            )
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
        "desire_seed_002": "180",
    }
    actual = {
        row["external_id"]: row["timer_seconds"]
        for row in _content_rows()
        if row["external_id"] in expected_timers
    }
    assert actual == expected_timers
