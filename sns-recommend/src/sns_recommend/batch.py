from __future__ import annotations

import argparse
import json
import logging
import signal
from threading import Event as StopEvent
from types import FrameType

from .events import Event, accept_event
from .db import source_connection

logger = logging.getLogger(__name__)


def poll_once(batch_size: int = 100) -> dict[str, int]:
    """Commit events/jobs before acknowledging the source Outbox."""
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    delivered = 0
    with source_connection() as conn:
        rows = conn.execute(
            """SELECT id,event FROM recommend_outbox WHERE delivered_at IS NULL
            ORDER BY created_at,id LIMIT %s FOR UPDATE SKIP LOCKED""",
            (batch_size,),
        ).fetchall()
        for row in rows:
            accept_event(Event.model_validate(row["event"]))
            conn.execute("UPDATE recommend_outbox SET delivered_at=now() WHERE id=%s", (row["id"],))
            delivered += 1
    return {"delivered": delivered}


def run_poller() -> None:
    stop = StopEvent()

    def shutdown(signum: int, frame: FrameType | None) -> None:
        stop.set()

    previous = {sig: signal.signal(sig, shutdown) for sig in (signal.SIGINT, signal.SIGTERM)}
    delay = 3
    try:
        while not stop.is_set():
            try:
                result = poll_once()
                if result["delivered"]:
                    logger.info("delivered=%s", result["delivered"])
            except Exception:
                logger.exception("Outbox batch failed; retrying in %ss", delay)
                stop.wait(delay)
                delay = min(delay * 2, 30)
            else:
                stop.wait(3)
                delay = 3
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume the SNS Outbox independently of FastAPI")
    parser.add_argument("--once", action="store_true", help="process one batch and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.once:
        print(json.dumps(poll_once()))
    else:
        run_poller()
