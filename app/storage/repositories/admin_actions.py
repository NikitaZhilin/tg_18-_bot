from __future__ import annotations

import json

from app.storage import Database


class AdminActionRepository:
    def __init__(self, db: Database):
        self.db = db

    def record(self, admin_user_id: int, action_type: str, target_type: str, target_id: str | None, details: dict) -> None:
        self.db.execute(
            """
            INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (admin_user_id, action_type, target_type, target_id, json.dumps(details, ensure_ascii=False)),
        )
