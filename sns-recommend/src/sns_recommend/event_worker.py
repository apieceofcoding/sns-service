from __future__ import annotations

import argparse
import json
import logging
import signal
from threading import Event
from types import FrameType

from .db import connection, source_connection
from .event_queue import enqueue, schedule_active
from .indexing import index_changes
from .sync_cursor import load_position, next_position, save_position, settled_before

logger = logging.getLogger(__name__)
BATCH_SIZE = 1000
NIL_UUID = "00000000-0000-0000-0000-000000000000"
# Changed rows per SNS table, oldest first. Each source row becomes one user_events row.
ACTION_SOURCES = (
    (
        "likes",
        "0",
        """SELECT 'like:'||id AS source_key,'like' AS action,user_id,post_id,
        created_at AT TIME ZONE 'UTC' AS occurred_at,deleted_at AT TIME ZONE 'UTC' AS removed_at,
        modified_at AT TIME ZONE 'UTC' AS changed_at,id::text AS cursor_id
        FROM likes WHERE (modified_at,id)>(%s::timestamp,%s::bigint)
        ORDER BY modified_at,id LIMIT %s""",
    ),
    (
        "posts",
        "0",
        """SELECT CASE WHEN parent_id IS NOT NULL THEN 'reply' ELSE 'repost' END||':'||id
        AS source_key,CASE WHEN parent_id IS NOT NULL THEN 'reply' ELSE 'repost' END AS action,
        user_id,COALESCE(parent_id,repost_id) AS post_id,
        created_at AT TIME ZONE 'UTC' AS occurred_at,deleted_at AT TIME ZONE 'UTC' AS removed_at,
        modified_at AT TIME ZONE 'UTC' AS changed_at,id::text AS cursor_id
        FROM posts WHERE (parent_id IS NOT NULL OR repost_id IS NOT NULL)
        AND (modified_at,id)>(%s::timestamp,%s::bigint)
        ORDER BY modified_at,id LIMIT %s""",
    ),
    (
        "post_actions",
        NIL_UUID,
        """SELECT action||':'||id AS source_key,action,user_id,post_id,
        created_at AS occurred_at,NULL::timestamptz AS removed_at,
        created_at AS changed_at,id::text AS cursor_id
        FROM post_actions WHERE (created_at,id)>(%s::timestamptz,%s::uuid)
        ORDER BY created_at,id LIMIT %s""",
    ),
)
# These actions change what the user is interested in, so the list should be rebuilt.
REFRESH_ACTIONS = {"like", "reply", "repost", "click"}


def sync_source(name, first_id, query):
    """Copy changed rows until a batch has news. Events and the cursor commit together."""
    with connection() as conn:
        position = load_position(conn, name, first_id)
    # The saved cursor stays behind the overlap window, but reading must still move through it.
    reading = position
    while True:
        with source_connection() as source:
            settled = settled_before(source)
            rows = source.execute(query, (*reading, BATCH_SIZE)).fetchall()
        with connection() as conn:
            known = {
                row["source_key"]: row["removed_at"]
                for row in conn.execute(
                    "SELECT source_key,removed_at FROM user_events WHERE source_key=ANY(%s)",
                    ([row["source_key"] for row in rows],),
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
            position = next_position(rows, position, settled, first_id)
            save_position(conn, name, position)
        if changed or len(rows) < BATCH_SIZE:
            return changed
        reading = rows[-1]["changed_at"], rows[-1]["cursor_id"]


def sync_events() -> int:
    changed = [row for source in ACTION_SOURCES for row in sync_source(*source)]
    for user_id in {row["user_id"] for row in changed if row["action"] in REFRESH_ACTIONS}:
        enqueue(user_id)
    return len(changed)


def poll_once() -> dict[str, int]:
    # A model failure in indexing must not hold back recorded actions, so it runs last.
    events = sync_events()
    scheduled = schedule_active()["scheduled"]
    indexed = index_changes()["indexed"]
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
