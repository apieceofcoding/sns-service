from __future__ import annotations

import logging
import time

from .config import settings
from .db import connection
from .feed import WANTED, current_created_at, redis_client
from .generation import generate

logger = logging.getLogger(__name__)
INTERVAL_SECONDS = 30


def due_users() -> list[int]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT DISTINCT user_id FROM user_events
            WHERE occurred_at>now()-interval '30 minutes'"""
        ).fetchall()
    due = {int(u) for u in redis_client().spop(WANTED, 1000) or []}
    for row in rows:
        created_at = current_created_at(row["user_id"])
        if created_at is None or time.time() - created_at >= settings().refresh_seconds:
            due.add(row["user_id"])
    return sorted(due)


def run_once() -> int:
    generated = 0
    for user_id in due_users():
        try:
            generate(user_id)
            generated += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("User %s failed: %s", user_id, type(exc).__name__)
    return generated


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            generated = run_once()
            if generated:
                logger.info("generated=%s", generated)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Worker retry: %s", type(exc).__name__)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
