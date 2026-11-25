import logging

import psycopg
from fastapi import FastAPI, HTTPException, Query

from .feed import read_feed
from .measurement import metrics, record_served

app = FastAPI(title="SNS Recommend", version="0.1.0")
logger = logging.getLogger(__name__)


@app.get("/metrics")
def measurements():
    return metrics()


@app.get("/internal/feeds/{user_id}")
def feed(
    user_id: int,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, max_length=512),
):
    try:
        result = read_feed(user_id, limit, cursor)
        try:
            record_served(user_id, result)
        except psycopg.Error as exc:
            logger.warning("Served posts not recorded: %s", type(exc).__name__)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
