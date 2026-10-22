from __future__ import annotations

from sns_recommend.core.config import settings
from sns_recommend.storage.event_queue import enqueue
from sns_recommend.storage.postgres import connection, source_connection


def schedule_active() -> dict[str, int]:
    with connection() as conn:
        users = conn.execute(
            "SELECT user_id FROM profiles WHERE active_at>now()-interval '30 minutes'"
        ).fetchall()
    scheduled = 0
    for user in users:
        with source_connection() as conn:
            recent = conn.execute(
                """SELECT 1 FROM recommend_events WHERE user_id=%s AND action='recommend.requested'
                AND created_at>now()-make_interval(secs=>%s) LIMIT 1""",
                (user["user_id"], settings().refresh_seconds),
            ).fetchone()
        if not recent and enqueue("recommend.requested", user["user_id"], throttle=True):
            scheduled += 1
    return {"scheduled": scheduled}
