from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from app.storage.database import Database


# An unfinished admin dialog older than this is forgotten, so a message typed
# days later is not taken as the next step (card title, password, ...).
STATE_TTL_MINUTES = 120


class SQLiteFSMStorage(BaseStorage):
    def __init__(self, db: Database, state_ttl_minutes: int = STATE_TTL_MINUTES):
        self.db = db
        self.state_ttl_minutes = state_ttl_minutes

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
            SELECT state, updated_at < datetime('now', ?) AS expired
            FROM fsm_states
            WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND thread_id = ?
              AND business_connection_id = ? AND destiny = ?
            """,
            (f"-{int(self.state_ttl_minutes)} minutes", *self._key_values(key)),
        )
        if not row or row["state"] is None:
            return None
        if row["expired"]:
            await self.set_state(key, None)
            await self.set_data(key, {})
            return None
        return str(row["state"])

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
