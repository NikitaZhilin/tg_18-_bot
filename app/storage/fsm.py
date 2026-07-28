from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from app.storage.database import Database


class SQLiteFSMStorage(BaseStorage):
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _key_values(key: StorageKey) -> tuple[int, int, int, int, str, str]:
        return (
            key.bot_id,
            key.chat_id,
            key.user_id,
            key.thread_id or 0,
            key.business_connection_id or "",
            key.destiny,
        )

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_value = state.state if isinstance(state, State) else state
        self.db.execute(
            """
            INSERT INTO fsm_states (
                bot_id, chat_id, user_id, thread_id,
                business_connection_id, destiny, state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (
                bot_id, chat_id, user_id, thread_id,
                business_connection_id, destiny
            ) DO UPDATE SET
                state = excluded.state,
                updated_at = CURRENT_TIMESTAMP
            """,
            (*self._key_values(key), state_value),
        )

    async def get_state(self, key: StorageKey) -> str | None:
        row = self.db.fetchone(
            """
            SELECT state
            FROM fsm_states
            WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND thread_id = ?
              AND business_connection_id = ? AND destiny = ?
            """,
            self._key_values(key),
        )
        return str(row["state"]) if row and row["state"] is not None else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        serialized = json.dumps(dict(data), ensure_ascii=False, separators=(",", ":"))
        self.db.execute(
            """
            INSERT INTO fsm_states (
                bot_id, chat_id, user_id, thread_id,
                business_connection_id, destiny, data_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (
                bot_id, chat_id, user_id, thread_id,
                business_connection_id, destiny
            ) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (*self._key_values(key), serialized),
        )

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        row = self.db.fetchone(
            """
            SELECT data_json
            FROM fsm_states
            WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND thread_id = ?
              AND business_connection_id = ? AND destiny = ?
            """,
            self._key_values(key),
        )
        if not row:
            return {}
        data = json.loads(str(row["data_json"]))
        return data if isinstance(data, dict) else {}

    async def close(self) -> None:
        return None
