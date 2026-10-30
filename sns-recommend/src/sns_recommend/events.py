from __future__ import annotations

from .db import source_connection


def excluded_ids(user_id: int) -> set[int]:
    with source_connection() as original:
        rows = original.execute(
            """SELECT DISTINCT post_id FROM recommend_events WHERE user_id=%s
            AND action IN ('impression','not_interested') AND created_at<=now()""",
            (user_id,),
        ).fetchall()
    return {row["post_id"] for row in rows}
