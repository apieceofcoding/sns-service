from fastapi import FastAPI, HTTPException, Query

from .feed import read_feed

app = FastAPI(title="SNS Recommend", version="0.1.0")


@app.get("/internal/feeds/{user_id}")
def feed(
    user_id: int,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, max_length=512),
):
    try:
        return read_feed(user_id, limit, cursor)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
