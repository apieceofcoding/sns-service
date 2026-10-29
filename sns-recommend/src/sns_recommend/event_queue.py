from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from .config import settings
from .db import connection, source_connection

EventRecord = dict[str, Any]


def enqueue(action: str, user_id: int, throttle: bool = False) -> str | None:
    with source_connection() as conn:
        # Serialize requests for one user, including the minimum refresh interval.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (user_id,))
        if throttle:
            recent = conn.execute(
                """SELECT id FROM recommend_events WHERE action=%s AND user_id=%s
                AND created_at>now()-make_interval(secs=>%s) LIMIT 1""",
                (action, user_id, settings().minimum_refresh_seconds),
            ).fetchone()
            if recent:
                return None
        row = conn.execute(
            """INSERT INTO recommend_events(action,user_id) VALUES (%s,%s)
            ON CONFLICT DO NOTHING RETURNING id""",
            (action, user_id),
        ).fetchone()
        if not row:
            row = conn.execute(
                """SELECT id FROM recommend_events WHERE action=%s AND user_id=%s
                AND processed_at IS NULL AND claim_id IS NULL ORDER BY created_at,id LIMIT 1""",
                (action, user_id),
            ).fetchone()
    return str(row["id"]) if row else None


def claim(actions: Sequence[str], event_id: str | None = None) -> EventRecord | None:
    with source_connection() as conn:
        row = conn.execute(
            """SELECT * FROM recommend_events WHERE action=ANY(%s) AND processed_at IS NULL
            AND (%s::uuid IS NULL OR id=%s::uuid)
            AND (locked_until IS NULL OR locked_until<=now())
            ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1""",
            (list(actions), event_id, event_id),
        ).fetchone()
        if row is None:
            return None
        row["claim_id"] = uuid4()
        row["locked_until"] = datetime.now(UTC) + timedelta(seconds=settings().lease_seconds)
        conn.execute(
            "UPDATE recommend_events SET claim_id=%s,locked_until=%s WHERE id=%s",
            (row["claim_id"], row["locked_until"], row["id"]),
        )
    return row


def renew(event: EventRecord) -> None:
    with source_connection() as conn:
        row = conn.execute(
            """UPDATE recommend_events SET locked_until=now()+make_interval(secs=>%s)
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
    with source_connection() as conn:
        return (
            conn.execute(
                """UPDATE recommend_events SET processed_at=now() WHERE id=%s AND claim_id=%s
            AND processed_at IS NULL AND locked_until>now() RETURNING id""",
                (event["id"], event["claim_id"]),
            ).fetchone()
            is not None
        )


def retry(event: EventRecord) -> None:
    with source_connection() as conn:
        conn.execute(
            """UPDATE recommend_events SET locked_until=now()+interval '30 seconds'
            WHERE id=%s AND claim_id=%s AND processed_at IS NULL""",
            (event["id"], event["claim_id"]),
        )


def allocate_generation(conn: Any, user_id: int) -> int:
    row = conn.execute(
        """INSERT INTO profiles(user_id,generation) VALUES (%s,%s)
        ON CONFLICT(user_id) DO UPDATE SET generation=GREATEST(profiles.generation+1,EXCLUDED.generation) RETURNING generation""",
        (user_id, time.time_ns() // 1000),
    ).fetchone()
    return row["generation"]


def current_generation(conn: Any, user_id: int) -> int:
    conn.execute("INSERT INTO profiles(user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    return conn.execute(
        "SELECT generation FROM profiles WHERE user_id=%s FOR UPDATE", (user_id,)
    ).fetchone()["generation"]


def migrate_legacy() -> None:
    """Move legacy history and unfinished work before dropping the two old tables."""
    with connection() as old:
        has_events = old.execute("SELECT to_regclass('events') AS name").fetchone()["name"]
        has_jobs = old.execute("SELECT to_regclass('jobs') AS name").fetchone()["name"]
        has_exclusions = old.execute("SELECT to_regclass('exclusions') AS name").fetchone()["name"]
        excluded = old.execute("SELECT * FROM exclusions").fetchall() if has_exclusions else []
        history = old.execute("SELECT * FROM events").fetchall() if has_events else []
        work = old.execute("SELECT * FROM jobs").fetchall() if has_jobs else []
        with source_connection() as conn:
            for row in history:
                version = (
                    row["payload"].get("version", 1) if row["kind"].startswith("post.") else None
                )
                conn.execute(
                    """INSERT INTO recommend_events(id,action,user_id,post_id,version,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (
                        row["event_id"],
                        row["kind"],
                        row["user_id"],
                        row["post_id"],
                        version,
                        row["occurred_at"],
                    ),
                )
            for row in excluded:
                conn.execute(
                    "INSERT INTO recommend_events(action,user_id,post_id,processed_at) VALUES (%s,%s,%s,now())",
                    (row["reason"], row["user_id"], row["post_id"]),
                )
            for row in work:
                if row["status"] in ("done", "superseded"):
                    continue
                action = {
                    "index": "post.updated",
                    "profile": "recommend.requested",
                    "build": "recommend.requested",
                }[row["kind"]]
                conn.execute(
                    """INSERT INTO recommend_events(id,action,user_id,post_id,version,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (
                        row["id"],
                        action,
                        row["user_id"],
                        row["post_id"],
                        row["payload"].get("version", 1) if action == "post.updated" else None,
                        row["created_at"],
                    ),
                )
        if has_events or has_jobs or has_exclusions:
            with source_connection() as original:
                original.execute("""INSERT INTO recommend_events(action,post_id,version)
                    SELECT CASE WHEN deleted_at IS NULL THEN 'post.updated' ELSE 'post.deleted' END,
                    id,content_version FROM posts ON CONFLICT DO NOTHING""")
            if old.execute("SELECT to_regclass('post_embeddings') AS name").fetchone()["name"]:
                old.execute("UPDATE post_embeddings SET content_version=0")
        if has_exclusions:
            old.execute("DROP TABLE exclusions")
        if has_jobs:
            old.execute("DROP TABLE jobs")
        if has_events:
            old.execute("DROP TABLE events")


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
