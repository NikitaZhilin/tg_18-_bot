from __future__ import annotations

import asyncio

from app.handlers import game
from app.keyboards.game import main_menu, tod_choice_menu
from app.services.game_service import GameService
from app.services.safety_service import SafetyService
from tests.helpers import import_seed, make_config, migrated_db
from tests.test_ux_polish import CHAT, FakeCallback, _datas


def _service(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    config = make_config(tmp_path)
    return db, config, GameService(db, config)


def test_random_card_works_without_an_open_game(tmp_path):
    db, config, service = _service(tmp_path)
    callback = FakeCallback("game:roulette")
    asyncio.run(game.cb_roulette(callback, config, service))
    assert service.status(CHAT, None)["has_active_turn"]
    assert not any(alert for _, alert in callback.answers)


def test_random_card_works_right_after_ending_the_game(tmp_path):
    db, config, service = _service(tmp_path)
    service.ensure_session(CHAT, None)
    SafetyService(db).end_game(CHAT, None, 111)
    assert service.active_session(CHAT, None) is None
    callback = FakeCallback("game:roulette")
    asyncio.run(game.cb_roulette(callback, config, service))
    assert service.status(CHAT, None)["has_active_turn"]


def test_truth_or_dare_is_in_the_main_menu():
    assert "tod:menu" in _datas(main_menu())
    datas = _datas(tod_choice_menu(3, "medium"))
    assert {"tod:draw:3:medium:question", "tod:draw:3:medium:task"} <= set(datas)


def test_truth_gives_a_question_and_dare_gives_a_task(tmp_path):
    db, config, service = _service(tmp_path)
    service.ensure_session(CHAT, None)
    truth = service.draw_truth_or_dare(CHAT, None, 111, level=3, intensity="medium", category="question")
    assert truth.card.category == "question" and truth.card.level == 3
    service.finish_turn(CHAT, None, 111)
    dare = service.draw_truth_or_dare(CHAT, None, 222, level=3, intensity="medium", category="task")
    assert dare.card.category == "task" and dare.card.level == 3 and dare.card.intensity == "medium"


def test_after_done_the_next_player_gets_the_same_choice(tmp_path):
    db, config, service = _service(tmp_path)
    draw = FakeCallback("tod:draw:4:hard:task")
    asyncio.run(game.cb_tod_draw(draw, config, service))
    turn_id = service.status(CHAT, None)["active_turn_id"]
    assert turn_id
    done = FakeCallback(f"game:done:{turn_id}", message=draw.message, bot=draw.bot)
    asyncio.run(game.cb_done(done, config, service))
    _, text, markup = done.bot.sent[-1]
    assert "Правда или действие" in text and "B" in text
    assert "tod:draw:4:hard:question" in _datas(markup)


def test_truth_falls_back_to_other_intensity_when_questions_run_out(tmp_path):
    db, config, service = _service(tmp_path)
    service.ensure_session(CHAT, None)
    players = [111, 222]
    seen = []
    for i in range(12):
        result = service.draw_truth_or_dare(CHAT, None, players[i % 2], level=3, intensity="light", category="question")
        seen.append(result.card.intensity)
        service.finish_turn(CHAT, None, players[i % 2])
    assert seen.count("light") == 8 and len(set(seen)) > 1


def test_replaced_card_stays_in_truth_or_dare_mode(tmp_path):
    db, config, service = _service(tmp_path)
    service.ensure_session(CHAT, None)
    first = service.draw_truth_or_dare(CHAT, None, 111, level=3, intensity="hard", category="task")
    second = service.replace_active_card(CHAT, None, 111)
    assert service.turn_play_mode(first.turn_id) == service.turn_play_mode(second.turn_id) == "tod:3:hard"
