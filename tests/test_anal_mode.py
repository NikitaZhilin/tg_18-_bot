from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from app.handlers import game_settings
from app.keyboards.game import main_menu
from tests.helpers import import_seed, make_config, migrated_db
from tests.test_ux_polish import CHAT, FakeCallback, _datas
from app.services.game_service import GameService


def _service(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_config(tmp_path)
    service = GameService(db, config)
    service.ensure_session(CHAT, None)
    return db, config, service


def _draw_all(db, service, **kwargs):
    titles = []
    while True:
        player = service.status(CHAT, None)["current_player_id"]
        try:
            result = service.draw_card(CHAT, None, player, **kwargs)
        except Exception:
            return titles
        tags = db.fetchone("SELECT risk_tags FROM cards WHERE id = ?", (result.card.id,))["risk_tags"]
        titles.append((result.card.external_id, tags))
        service.finish_turn(CHAT, None, player)


def test_main_menu_shows_the_anal_switch_with_its_state():
    menu = main_menu(anal_mode="off")
    assert "anal:menu" in _datas(menu)
    assert any("🍑 Анал: 🚫" in button.text for row in menu.inline_keyboard for button in row)


def test_anal_off_hides_every_card_where_anal_is_required(tmp_path):
    db, config, service = _service(tmp_path)
    service.set_anal_mode(CHAT, None, "off")
    drawn = _draw_all(db, service, level=3, category=None)
    assert drawn and not any("anal" in tags for _, tags in drawn)


def test_anal_for_her_only_hides_pegging_but_keeps_her_cards(tmp_path):
    db, config, service = _service(tmp_path)
    service.set_anal_mode(CHAT, None, "her")
    drawn = _draw_all(db, service, level=3, category="task")
    ids = {card_id for card_id, _ in drawn}
    assert "task_l3_v2_032" not in ids  # strap-on for him
    assert "task_l3_v3_08" in ids  # her anal with the clit vibe


def test_anal_for_him_only_hides_her_anal_cards(tmp_path):
    db, config, service = _service(tmp_path)
    service.set_anal_mode(CHAT, None, "him")
    drawn = _draw_all(db, service, level=3, category="task")
    ids = {card_id for card_id, _ in drawn}
    assert "task_l3_v3_08" not in ids
    assert "task_l3_v2_032" in ids


def test_saving_boundaries_keeps_the_anal_mode(tmp_path):
    db, config, service = _service(tmp_path)
    service.boundaries_draft(CHAT, None, 111)  # draft opened before the switch
    service.set_anal_mode(CHAT, None, "off")
    service.toggle_boundaries_draft(CHAT, None, 111, "wax")
    service.save_boundaries_draft(CHAT, None, 111)
    assert service.anal_mode(CHAT, None) == "off"
    assert "wax" in service.boundaries_for_active_session(CHAT, None)


def test_anal_buttons_switch_mode_and_return_home(tmp_path):
    db, config, service = _service(tmp_path)
    callback = FakeCallback("anal:set:her")
    asyncio.run(game_settings.cb_anal_set(callback, config, service))
    text, markup = callback.message.edits[-1]
    assert text.startswith("🍑 Анал: 👩")
    assert any("только ей" in button.text for row in markup.inline_keyboard for button in row)


def test_cards_are_plain_text_and_anal_tags_are_known():
    from app.labels import RISK_TAG_NAMES

    with Path("content/cards.csv").open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    tags = {tag for row in rows for tag in row["risk_tags"].split(",") if tag.startswith("anal")}
    assert tags <= set(RISK_TAG_NAMES)
    penalty = next(row for row in rows if row["title"] == "Надувная до предела")
    assert "\n" not in penalty["text"] and not penalty["text"].startswith("Контекст")
