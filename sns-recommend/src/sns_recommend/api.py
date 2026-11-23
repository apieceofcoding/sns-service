from fastapi import FastAPI, HTTPException, Query

from . import source
from .events import excluded_ids
from .feed import read_feed

app = FastAPI(title="SNS Recommend", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/internal/feeds/{user_id}")
def feed(
    user_id: int,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, max_length=512),
):
    try:
        return read_feed(user_id, limit, cursor, excluded_ids(user_id), alive=source.alive_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
