from __future__ import annotations

import argparse
import json
import logging
import time

import psycopg
from redis.exceptions import RedisError

from .event_queue import claim, finish, heartbeat, retry
from .graph import run_graph

logger = logging.getLogger(__name__)


def run_one() -> bool:
    event = claim(("recommend.requested",))
    if event is None:
        return False
    try:
        with heartbeat(event):
            run_graph(event)

    except Exception as exc:
        logger.warning("Event %s failed: %s",event["id"],type(exc).__name__)
        retry(event)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true")
    args = parser.parse_args()
    if args.once:
        print(json.dumps({"processed":run_one()}))
    else:
        while True:
            try:
                processed = run_one()
            except (psycopg.Error,RedisError) as exc:
                logger.warning("Worker storage unavailable: %s",type(exc).__name__)
                processed = False
            if not processed:
                time.sleep(1)


if __name__ == "__main__":
    main()
