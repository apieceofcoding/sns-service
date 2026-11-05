from __future__ import annotations

import argparse
import json
import logging
import signal
from threading import Event
from types import FrameType

from .db import connection, source_connection
from .event_queue import enqueue, schedule_active
from .indexing import index_posts, posts_needing_index

logger = logging.getLogger(__name__)
# Current actions in the SNS database. Each source row becomes one user_events row.
SOURCE_ACTIONS = """
    SELECT 'like:'||id AS source_key,'like' AS action,user_id,post_id,
        created_at AT TIME ZONE 'UTC' AS occurred_at,deleted_at AT TIME ZONE 'UTC' AS removed_at
    FROM likes
    UNION ALL
    SELECT 'reply:'||id,'reply',user_id,parent_id,
        created_at AT TIME ZONE 'UTC',deleted_at AT TIME ZONE 'UTC'
    FROM posts WHERE parent_id IS NOT NULL
    UNION ALL
    SELECT 'repost:'||id,'repost',user_id,repost_id,
        created_at AT TIME ZONE 'UTC',deleted_at AT TIME ZONE 'UTC'
    FROM posts WHERE repost_id IS NOT NULL
    UNION ALL
    SELECT action||':'||id,action,user_id,post_id,created_at,NULL
    FROM post_actions
"""
# These actions change what the user is interested in, so the list should be rebuilt.
REFRESH_ACTIONS = {"like", "reply", "repost", "click"}


def sync_events() -> int:
    with source_connection() as source:
        rows = source.execute(SOURCE_ACTIONS).fetchall()
    with connection() as conn:
        known = {
            row["source_key"]: row["removed_at"]
            for row in conn.execute(
                "SELECT source_key,removed_at FROM user_events WHERE source_key IS NOT NULL"
            ).fetchall()
        }
        changed = [
            row
            for row in rows
            if row["source_key"] not in known or known[row["source_key"]] != row["removed_at"]
        ]
        for row in changed:
            conn.execute(
                """INSERT INTO user_events(source_key,action,user_id,post_id,occurred_at,removed_at)
                VALUES (%(source_key)s,%(action)s,%(user_id)s,%(post_id)s,
                %(occurred_at)s,%(removed_at)s)
                ON CONFLICT(source_key) DO UPDATE SET removed_at=EXCLUDED.removed_at""",
                row,
            )
    for user_id in {row["user_id"] for row in changed if row["action"] in REFRESH_ACTIONS}:
        enqueue(user_id)
    return len(changed)


def poll_once() -> dict[str, int]:
    # A model failure in indexing must not hold back recorded actions, so it runs last.
    events = sync_events()
    scheduled = schedule_active()["scheduled"]
    post_ids = posts_needing_index()
    indexed = index_posts(post_ids)["indexed"] if post_ids else 0
    return {
        "processed": events + indexed,
        "events": events,
        "indexed": indexed,
        "scheduled": scheduled,
    }


def run_poller() -> None:
    stop = Event()

    def shutdown(signum: int, frame: FrameType | None) -> None:
        stop.set()

    previous = {sig: signal.signal(sig, shutdown) for sig in (signal.SIGINT, signal.SIGTERM)}
    delay = 3
    try:
        while not stop.is_set():
            try:
                result = poll_once()
                if result["processed"]:
                    logger.info("processed=%s", result["processed"])
                delay = 3
                if not result["processed"]:
                    stop.wait(3)
            except Exception as exc:
                logger.warning("Event worker retry in %ss: %s", delay, type(exc).__name__)
                stop.wait(delay)
                delay = min(delay * 2, 30)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy SNS changes into the recommend database")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.once:
        print(json.dumps(poll_once()))
    else:
        run_poller()
