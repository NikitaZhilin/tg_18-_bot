from __future__ import annotations

import random
import sqlite3

from app.domain import PickFilter, PickedCard, intensity_allowed, int_to_bool, parse_json_list
from app.storage import Database


class NoCardsAvailable(RuntimeError):
    pass


class CardPicker:
    ITEM_CHANCES = {1: 0.25, 2: 0.55, 3: 0.85}

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
        if not filters.allow_restricted_content:
            where.append(
                """
                NOT EXISTS (
                    SELECT 1 FROM card_collection_items restricted
                    WHERE restricted.card_id = c.id
                      AND restricted.collection_code = 'restricted_content'
                )
                """
            )

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
        weighted_candidates = [
            row
            for row in candidates
            for _ in range(self._card_weight(executor, filters.session_id, int(row["id"])))
        ]
        row = self.rng.choice(weighted_candidates)
        return self._row_to_card(row, filters.session_id, executor)

    def for_turn(self, turn_id: int, conn: sqlite3.Connection | None = None) -> PickedCard | None:
        executor = conn or self.db
        row = executor.execute(
            """
            SELECT c.*, t.session_id, t.selected_item_code
            FROM turns t
            JOIN cards c ON c.id = t.card_id
            WHERE t.id = ?
            """,
            (turn_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_card(
            row,
            int(row["session_id"]),
            executor,
            row["selected_item_code"],
            choose_item=False,
        )

    def _row_to_card(
        self,
        row: sqlite3.Row,
        session_id: int,
        executor: sqlite3.Connection | Database,
        selected_item_code: str | None = None,
        choose_item: bool = True,
    ) -> PickedCard:
        item = self._item_by_code(executor, selected_item_code) if selected_item_code else None
        if item is None and choose_item:
            item = self._pick_item(executor, session_id, row)
        display_number = int(
            executor.execute(
                """
                SELECT COUNT(*) AS number
                FROM cards numbered
                WHERE numbered.level = ?
                  AND numbered.category = ?
                  AND numbered.id <= ?
                """,
                (row["level"], row["category"], row["id"]),
            ).fetchone()["number"]
        )
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
            display_number=display_number,
            selected_item_code=item["code"] if item else None,
            selected_item_name=item["name"] if item else None,
            selected_item_usage=item["usage_text"] if item else None,
        )

    def _pick_item(
        self,
        executor: sqlite3.Connection | Database,
        session_id: int,
        card: sqlite3.Row,
    ) -> sqlite3.Row | None:
        rows = executor.execute(
            """
            SELECT i.code, i.name, i.usage_text, si.frequency,
                   CASE WHEN cri.item_code IS NULL THEN 0 ELSE 1 END AS is_required
            FROM session_items si
            JOIN items i ON i.code = si.item_code
            LEFT JOIN card_required_items cri
              ON cri.card_id = ? AND cri.item_code = i.code
            WHERE si.session_id = ?
              AND i.is_active = 1
              AND ? BETWEEN i.min_level AND i.max_level
              AND instr(',' || i.categories || ',', ',' || ? || ',') > 0
              AND (i.randomizable = 1 OR cri.item_code IS NOT NULL)
            ORDER BY i.code
            """,
            (card["id"], session_id, card["level"], card["category"]),
        ).fetchall()
        if not rows:
            return None
        required = [row for row in rows if int(row["is_required"])]
        if required:
            return self.rng.choice(required)
        eligible = [
            row
            for row in rows
            if self.rng.random() <= self.ITEM_CHANCES.get(int(row["frequency"]), 0.55)
        ]
        if not eligible:
            return None
        weighted = [row for row in eligible for _ in range(int(row["frequency"]))]
        return self.rng.choice(weighted)

    @staticmethod
    def _card_weight(executor: sqlite3.Connection | Database, session_id: int, card_id: int) -> int:
        row = executor.execute(
            """
            SELECT MIN(si.frequency) AS frequency
            FROM card_required_items cri
            JOIN session_items si
              ON si.item_code = cri.item_code AND si.session_id = ?
            WHERE cri.card_id = ?
            """,
            (session_id, card_id),
        ).fetchone()
        return int(row["frequency"] or 2)

    @staticmethod
    def _item_by_code(executor: sqlite3.Connection | Database, code: str) -> sqlite3.Row | None:
        return executor.execute(
            "SELECT code, name, usage_text FROM items WHERE code = ?",
            (code,),
        ).fetchone()
