import logging

import psycopg
from fastapi import FastAPI, HTTPException, Query
from redis.exceptions import RedisError

from . import source
from .events import excluded_ids
from .feed import read_feed
from .measurement import metrics, record_served

app = FastAPI(title="SNS Recommend", version="0.1.0")
logger = logging.getLogger(__name__)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def measurements(minutes: int = Query(60, ge=1, le=1440)):
    return metrics(minutes)


@app.get("/internal/feeds/{user_id}")
def feed(user_id: int, limit: int = Query(20, ge=1, le=50), cursor: str | None = Query(None, max_length=512)):
    try:
        excluded = excluded_ids(user_id)
        # Deleted posts are checked in the SNS database for this page.
        result = read_feed(user_id, limit, cursor, excluded, alive=source.alive_ids)
        if not source.user_exists(user_id):
            raise HTTPException(404, "unknown user")
        try:
            record_served(user_id, result)
        except psycopg.Error as exc:
            # The feed matters more than its record.
            logger.warning("Served posts not recorded: %s", type(exc).__name__)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(410, str(exc)) from exc
    except (RedisError, psycopg.Error) as exc:
        raise HTTPException(503, "feed unavailable; SNS should serve latest") from exc
