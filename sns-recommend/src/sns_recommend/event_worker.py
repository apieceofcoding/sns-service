from __future__ import annotations

import argparse
import json
import logging
import signal
from threading import Event
from types import FrameType

from .db import source_connection
from .event_queue import EventRecord, claim, finish, heartbeat, retry
from .indexing import index_posts

logger = logging.getLogger(__name__)
ACTIONS = ("post.updated", "post.deleted", "impression", "click", "like", "not_interested")


def handle(event: EventRecord) -> None:
    if event["action"].startswith("post."):
        with source_connection() as conn:
            row = conn.execute(
                "SELECT content_version FROM posts WHERE id=%s", (event["post_id"],)
            ).fetchone()
        # Every newer version is accompanied by a committed event from the same trigger.
        if row is not None and row["content_version"] > event["version"]:
            return
        index_posts([event["post_id"]])
    # User actions are the history itself. Retrieval and reranking read it directly.


def poll_once(batch_size: int = 100) -> dict[str, int]:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    processed = 0
    for _ in range(batch_size):
        event = claim(ACTIONS)
        if event is None:
            break
        try:
            with heartbeat(event):
                handle(event)
            if not finish(event):
                raise RuntimeError("event lease lost")
            processed += 1
        except Exception as exc:
            logger.warning("Event %s failed: %s", event["id"], type(exc).__name__)
            retry(event)
    return {"processed": processed}


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
    parser = argparse.ArgumentParser(
        description="Process recommend_events independently of FastAPI"
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.once:
        print(json.dumps(poll_once()))
    else:
        run_poller()
