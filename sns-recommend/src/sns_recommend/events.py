from __future__ import annotations

from datetime import datetime

from .db import connection


def excluded_ids(user_id: int, before: datetime | None = None) -> set[int]:
    """Posts already shown to the user, optionally only those shown before `before`."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT post_id FROM user_events WHERE user_id=%s
            AND action='impression' AND removed_at IS NULL
            AND (%s::timestamptz IS NULL OR occurred_at<%s)""",
            (user_id, before, before),
        ).fetchall()
    return {row["post_id"] for row in rows}
