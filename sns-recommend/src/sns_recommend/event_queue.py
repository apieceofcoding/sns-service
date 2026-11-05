from __future__ import annotations

import time

from .config import settings
from .db import connection
from .feed import current_created_at


def enqueue(user_id: int, throttle: bool = False) -> str | None:
    """Keep one pending recommendation request per user."""
    with connection() as conn:
        # Serialize requests for one user, including the minimum refresh interval.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (user_id,))
        if throttle:
            recent = conn.execute(
                """SELECT id FROM user_events WHERE action='recommend.requested' AND user_id=%s
                AND occurred_at>now()-make_interval(secs=>%s) LIMIT 1""",
                (user_id, settings().minimum_refresh_seconds),
            ).fetchone()
            if recent:
                return None
        row = conn.execute(
            """INSERT INTO user_events(action,user_id) VALUES ('recommend.requested',%s)
            ON CONFLICT DO NOTHING RETURNING id""",
            (user_id,),
        ).fetchone()
        if not row:
            row = conn.execute(
                """SELECT id FROM user_events WHERE action='recommend.requested' AND user_id=%s
                AND processed_at IS NULL LIMIT 1""",
                (user_id,),
            ).fetchone()
    return str(row["id"]) if row else None


def schedule_active() -> dict[str, int]:
    """Request a new list for users who recently saw posts and whose list is missing or old."""
    with connection() as conn:
        users = conn.execute(
            """SELECT DISTINCT user_id FROM user_events WHERE action='impression'
            AND occurred_at>now()-interval '30 minutes'"""
        ).fetchall()
    scheduled = 0
    for user in users:
        created_at = current_created_at(user["user_id"])
        fresh = created_at is not None and time.time() - created_at < settings().refresh_seconds
        if not fresh and enqueue(user["user_id"], throttle=True):
            scheduled += 1
    return {"scheduled": scheduled}
