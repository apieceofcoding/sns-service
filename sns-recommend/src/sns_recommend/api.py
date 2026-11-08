import psycopg
from fastapi import FastAPI, HTTPException, Query
from redis.exceptions import RedisError

from . import source
from .events import excluded_ids
from .feed import read_feed

app = FastAPI(title="SNS Recommend", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/internal/feeds/{user_id}")
def feed(user_id: int, limit: int = Query(20, ge=1, le=50), cursor: str | None = None):
    try:
        excluded = excluded_ids(user_id)
        # Deleted posts are checked in the SNS database for this page.
        result = read_feed(user_id, limit, cursor, excluded, alive=source.alive_ids)
        if not source.user_exists(user_id):
            raise HTTPException(404, "unknown user")
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(410, str(exc)) from exc
    except (RedisError, psycopg.Error) as exc:
        raise HTTPException(503, "feed unavailable; SNS should serve latest") from exc
