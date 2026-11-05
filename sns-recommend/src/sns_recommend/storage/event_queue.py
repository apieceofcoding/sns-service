from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from sns_recommend.core.config import settings
from sns_recommend.core.types import DatabaseConnection
from sns_recommend.storage.feeds import current_created_at
from sns_recommend.storage.postgres import connection

EventRecord = dict[str, Any]


def enqueue(user_id: int, throttle: bool = False) -> str | None:
    """Keep one waiting recommendation request per user."""
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
                AND processed_at IS NULL AND claim_id IS NULL LIMIT 1""",
                (user_id,),
            ).fetchone()
    return str(row["id"]) if row else None


def claim(actions: Sequence[str], event_id: str | None = None) -> EventRecord | None:
    with connection() as conn:
        row = conn.execute(
            """SELECT * FROM user_events WHERE action=ANY(%s) AND processed_at IS NULL
            AND (%s::uuid IS NULL OR id=%s::uuid)
            AND (locked_until IS NULL OR locked_until<=now())
            ORDER BY occurred_at,id FOR UPDATE SKIP LOCKED LIMIT 1""",
            (list(actions), event_id, event_id),
        ).fetchone()
        if row is None:
            return None
        row["claim_id"] = uuid4()
        row["locked_until"] = datetime.now(UTC) + timedelta(seconds=settings().lease_seconds)
        conn.execute(
            "UPDATE user_events SET claim_id=%s,locked_until=%s WHERE id=%s",
            (row["claim_id"], row["locked_until"], row["id"]),
        )
    return row


def renew(event: EventRecord) -> None:
    with connection() as conn:
        row = conn.execute(
            """UPDATE user_events SET locked_until=now()+make_interval(secs=>%s)
            WHERE id=%s AND claim_id=%s AND processed_at IS NULL AND locked_until>now()
            RETURNING id""",
            (settings().lease_seconds, event["id"], event["claim_id"]),
        ).fetchone()
        if row is None:
            raise RuntimeError("event lease lost")


@contextmanager
def heartbeat(event: EventRecord) -> Iterator[None]:
    stop = Event()
    lost: list[Exception] = []

    def extend() -> None:
        while not stop.wait(max(0.1, settings().lease_seconds / 3)):
            try:
                renew(event)
            except Exception as exc:
                lost.append(exc)
                return

    thread = Thread(target=extend, daemon=True)
    thread.start()
    try:
        yield
        if lost:
            raise RuntimeError("event lease renewal failed") from lost[0]
    finally:
        stop.set()
        thread.join(timeout=5)


def finish(event: EventRecord) -> bool:
    with connection() as conn:
        return (
            conn.execute(
                """UPDATE user_events SET processed_at=now() WHERE id=%s AND claim_id=%s
            AND processed_at IS NULL AND locked_until>now() RETURNING id""",
                (event["id"], event["claim_id"]),
            ).fetchone()
            is not None
        )


def retry(event: EventRecord) -> None:
    with connection() as conn:
        conn.execute(
            """UPDATE user_events SET locked_until=now()+interval '30 seconds'
            WHERE id=%s AND claim_id=%s AND processed_at IS NULL""",
            (event["id"], event["claim_id"]),
        )


def allocate_generation(conn: DatabaseConnection, user_id: int) -> int:
    row = conn.execute(
        """INSERT INTO profiles(user_id,generation) VALUES (%s,%s)
        ON CONFLICT(user_id) DO UPDATE SET generation=GREATEST(profiles.generation+1,EXCLUDED.generation) RETURNING generation""",
        (user_id, time.time_ns() // 1000),
    ).fetchone()
    return row["generation"]


def current_generation(conn: DatabaseConnection, user_id: int) -> int:
    conn.execute("INSERT INTO profiles(user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    return conn.execute(
        "SELECT generation FROM profiles WHERE user_id=%s FOR UPDATE", (user_id,)
    ).fetchone()["generation"]


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
