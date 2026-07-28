from __future__ import annotations

import asyncio

from aiogram.fsm.storage.base import StorageKey

from app.main import build_dispatcher, build_services
from app.services.game_service import GameService
from app.storage.fsm import SQLiteFSMStorage
from tests.helpers import make_config, migrated_db


def test_sqlite_fsm_survives_storage_recreation(tmp_path):
    db = migrated_db(tmp_path)
    key = StorageKey(
        bot_id=10,
        chat_id=-100,
        user_id=111,
        thread_id=7,
        destiny="admin",
    )

    async def write_and_read() -> None:
        first = SQLiteFSMStorage(db)
        await first.set_state(key, "AdminCard:add_text")
        await first.set_data(key, {"level": 4, "text": "Черновик"})

        second = SQLiteFSMStorage(db)
        assert await second.get_state(key) == "AdminCard:add_text"
        assert await second.get_data(key) == {"level": 4, "text": "Черновик"}

    asyncio.run(write_and_read())
    db.close()


def test_dispatcher_uses_sqlite_fsm_storage(tmp_path):
    db, services = build_services(make_config(tmp_path))
    dispatcher = build_dispatcher(services)
    assert isinstance(dispatcher.storage, SQLiteFSMStorage)
    db.close()


def test_inventory_and_boundary_drafts_survive_service_recreation(tmp_path):
    db = migrated_db(tmp_path)
    config = make_config(tmp_path)
    service = GameService(db, config)
    service.ensure_session(-100, 7)

    assert service.toggle_inventory_draft(-100, 7, 111, "ice") == {"ice": 1}
    assert service.toggle_boundaries_draft(-100, 7, 111, "impact") == {"impact"}

    restarted_service = GameService(db, config)
    assert restarted_service.inventory_draft(-100, 7, 111) == {"ice": 1}
    assert restarted_service.boundaries_draft(-100, 7, 111) == {"impact"}

    restarted_service.ensure_session(-100, 8)
    assert restarted_service.inventory_draft(-100, 8, 111) == {}
    assert restarted_service.boundaries_draft(-100, 8, 111) == set()

    restarted_service.save_inventory_draft(-100, 7, 111)
    restarted_service.save_boundaries_draft(-100, 7, 111)
    assert restarted_service.items_for_active_session(-100, 7) == {"ice": 1}
    assert restarted_service.boundaries_for_active_session(-100, 7) == {"impact"}
    assert db.fetchone(
        "SELECT 1 FROM session_setting_drafts WHERE user_id = 111 AND session_id = 1"
    ) is None
    db.close()
