from __future__ import annotations

import argparse
import json
import logging
import time

import psycopg
from redis.exceptions import RedisError

from sns_recommend.pipelines.graph import run_graph
from sns_recommend.storage.event_queue import claim, heartbeat, retry, schedule_active

logger = logging.getLogger(__name__)


def run_one() -> bool:
    event = claim()
    if event is None:
        return False
    try:
        with heartbeat(event):
            run_graph(event)
    except Exception as exc:
        logger.warning("Event %s failed: %s", event["id"], type(exc).__name__)
        retry(event)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        print(json.dumps({"processed": run_one()}))
    else:
        last_schedule = 0.0
        while True:
            try:
                if time.monotonic() - last_schedule >= 30:
                    schedule_active()
                    last_schedule = time.monotonic()
                processed = run_one()
            except (psycopg.Error, RedisError) as exc:
                logger.warning("Worker storage unavailable: %s", type(exc).__name__)
                processed = False
            if not processed:
                time.sleep(1)


if __name__ == "__main__":
    main()
