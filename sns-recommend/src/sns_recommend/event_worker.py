from __future__ import annotations

import argparse
import json
import logging
import signal
from threading import Event
from types import FrameType

from .db import connection, source_connection
from .indexing import index_changes
from .sync_cursor import load_position, next_position, save_position, settled_before

logger = logging.getLogger(__name__)
BATCH_SIZE = 1000
# Changed rows per SNS table, oldest first. Each source row becomes one user_events row.
ACTION_SOURCES = (
    (
        "likes",
        """SELECT 'like' AS action,user_id,post_id,
        created_at AT TIME ZONE 'UTC' AS occurred_at,deleted_at AT TIME ZONE 'UTC' AS removed_at,
        modified_at AT TIME ZONE 'UTC' AS changed_at,id AS source_id
        FROM likes WHERE (modified_at,id)>(%s::timestamp,%s::bigint)
        ORDER BY modified_at,id LIMIT %s""",
    ),
    (
        "posts",
        """SELECT CASE WHEN parent_id IS NOT NULL THEN 'reply' ELSE 'repost' END AS action,
        user_id,COALESCE(parent_id,repost_id) AS post_id,
        created_at AT TIME ZONE 'UTC' AS occurred_at,deleted_at AT TIME ZONE 'UTC' AS removed_at,
        modified_at AT TIME ZONE 'UTC' AS changed_at,id AS source_id
        FROM posts WHERE (parent_id IS NOT NULL OR repost_id IS NOT NULL)
        AND (modified_at,id)>(%s::timestamp,%s::bigint)
        ORDER BY modified_at,id LIMIT %s""",
    ),
    (
        "post_actions",
        # Read by arrival time. A late event keeps its original time but is not skipped.
        """SELECT action,user_id,post_id,
        created_at AS occurred_at,NULL::timestamptz AS removed_at,
        recorded_at AS changed_at,id AS source_id
        FROM post_actions WHERE (recorded_at,id)>(%s::timestamptz,%s::bigint)
        ORDER BY recorded_at,id LIMIT %s""",
    ),
)


def sync_source(name, query):
    """Copy changed rows until a batch has news. Events and the cursor commit together."""
    with connection() as conn:
        position = load_position(conn, name)
    # The saved cursor stays behind the overlap window, but reading must still move through it.
    reading = position
    while True:
        with source_connection() as source:
            settled = settled_before(source)
            rows = source.execute(query, (*reading, BATCH_SIZE)).fetchall()
        with connection() as conn:
            known = {
                (row["action"], row["source_id"]): row["removed_at"]
                for row in conn.execute(
                    "SELECT action,source_id,removed_at FROM user_events WHERE source_id=ANY(%s)",
                    ([row["source_id"] for row in rows],),
                ).fetchall()
            }
            changed = [
                row
                for row in rows
                if known.get((row["action"], row["source_id"]), "new") != row["removed_at"]
            ]
            conn.cursor().executemany(
                """INSERT INTO user_events(source_id,action,user_id,post_id,occurred_at,removed_at)
                VALUES (%(source_id)s,%(action)s,%(user_id)s,%(post_id)s,
                %(occurred_at)s,%(removed_at)s)
                ON CONFLICT(source_id,action) DO UPDATE SET removed_at=EXCLUDED.removed_at""",
                changed,
            )
            position = next_position(rows, position, settled)
            save_position(conn, name, position)
        if changed or len(rows) < BATCH_SIZE:
            return changed
        reading = rows[-1]["changed_at"], rows[-1]["source_id"]


def sync_events() -> int:
    return sum(len(sync_source(*source)) for source in ACTION_SOURCES)


def poll_once() -> dict[str, int]:
    # A model failure in indexing must not hold back recorded actions, so it runs last.
    events = sync_events()
    indexed = index_changes()["indexed"]
    return {"processed": events + indexed, "events": events, "indexed": indexed}


def drain() -> dict[str, int]:
    """Process until nothing is left. Used by --once and by the course steps."""
    total: dict[str, int] = {}
    while True:
        result = poll_once()
        for key, value in result.items():
            total[key] = total.get(key, 0) + value
        if not result["processed"]:
            return total


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
        print(json.dumps(drain()))
    else:
        run_poller()
