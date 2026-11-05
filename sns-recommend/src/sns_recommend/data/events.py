from __future__ import annotations

from sns_recommend.storage.postgres import connection


def excluded_ids(user_id: int) -> set[int]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT post_id FROM user_events WHERE user_id=%s
            AND action='impression' AND removed_at IS NULL""",
            (user_id,),
        ).fetchall()
    return {row["post_id"] for row in rows}
