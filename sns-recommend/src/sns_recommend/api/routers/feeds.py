from __future__ import annotations

import psycopg
from fastapi import APIRouter, HTTPException, Path, Query
from redis.exceptions import RedisError

from sns_recommend.core.types import FeedResponse
from sns_recommend.data.events import excluded_ids
from sns_recommend.storage import source
from sns_recommend.storage.feeds import MAX_CURSOR_LENGTH, read_feed
from sns_recommend.storage.event_queue import enqueue
from sns_recommend.storage.postgres import connection

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("/{user_id}")
def feed(
    user_id: int = Path(gt=0, le=2**63 - 1),
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, max_length=MAX_CURSOR_LENGTH),
) -> FeedResponse:
    try:
        with connection() as conn:
            excluded = excluded_ids(conn, user_id)
        # Deleted posts are checked in the SNS database, only for the IDs this page can show.
        result = read_feed(user_id, limit, cursor, excluded, alive=source.alive_ids)
        if not source.user_exists(user_id):
            raise HTTPException(404, "unknown user")
        with connection() as conn:
            conn.execute(
                """INSERT INTO profiles(user_id,active_at) VALUES (%s,now())
                ON CONFLICT(user_id) DO UPDATE SET active_at=now()""",
                (user_id,),
            )
            if not result["ready"] or result.get("stale") or not result["next_cursor"]:
                result["refresh_event"] = enqueue("recommend.requested", user_id, throttle=True)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(410, str(exc)) from exc
    except (RedisError, psycopg.Error) as exc:
        raise HTTPException(503, "feed unavailable; SNS should serve latest") from exc
