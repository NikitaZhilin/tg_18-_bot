from __future__ import annotations

import random
import sqlite3

from app.domain import PickFilter, PickedCard, intensity_allowed, int_to_bool, parse_json_list
from app.storage import Database


class NoCardsAvailable(RuntimeError):
    pass


class CardPicker:
    def __init__(self, db: Database, rng: random.Random | None = None):
        self.db = db
        self.rng = rng or random.Random()

    def pick(self, filters: PickFilter, conn: sqlite3.Connection | None = None) -> PickedCard:
        executor = conn or self.db
        where = [
            "c.is_enabled = 1",
            "c.review_status = 'approved'",
            """
            NOT EXISTS (
                SELECT 1 FROM used_cards u
                WHERE u.session_id = ? AND u.card_id = c.id
            )
            """,
            """
            NOT EXISTS (
                SELECT 1 FROM card_required_items cri
                WHERE cri.card_id = c.id
                  AND cri.item_code NOT IN (
                      SELECT item_code FROM session_items WHERE session_id = ?
                  )
            )
            """,
        ]
        params: list[object] = [filters.session_id, filters.session_id]
        if filters.level is not None:
            where.append("c.level = ?")
            params.append(filters.level)
        if filters.category is not None:
            where.append("c.category = ?")
            params.append(filters.category)
        if filters.intensity is not None:
            where.append("c.intensity = ?")
            params.append(filters.intensity)
        if not filters.allow_level_4:
            where.append("c.level < 4")

        rows = executor.execute(
            f"""
            SELECT c.*
            FROM cards c
            WHERE {" AND ".join(where)}
            """,
            params,
        ).fetchall()
        blocked_tags = {
            row["risk_tag"]
            for row in executor.execute(
                "SELECT risk_tag FROM session_blocked_tags WHERE session_id = ?",
                (filters.session_id,),
            ).fetchall()
        }
        candidates = []
        for row in rows:
            risk_tags = set(parse_json_list(row["risk_tags"]))
            avoid_if_tags = set(parse_json_list(row["avoid_if_tags"]))
            if not intensity_allowed(row["intensity"], filters.max_intensity):
                continue
            if blocked_tags.intersection(risk_tags) or blocked_tags.intersection(avoid_if_tags):
                continue
            candidates.append(row)

        if not candidates:
            raise NoCardsAvailable("no matching cards")
        row = self.rng.choice(candidates)
        return PickedCard(
            id=int(row["id"]),
            external_id=row["external_id"],
            level=int(row["level"]),
            category=row["category"],
            intensity=row["intensity"],
            title=row["title"],
            text=row["text"],
            timer_seconds=row["timer_seconds"],
            safety_level=row["safety_level"],
            risk_tags=tuple(parse_json_list(row["risk_tags"])),
            aftercare_required=int_to_bool(row["aftercare_required"]),
        )
