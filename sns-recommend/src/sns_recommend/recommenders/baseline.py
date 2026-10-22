from __future__ import annotations

from sns_recommend.storage import source
from sns_recommend.storage.feeds import publish
from sns_recommend.storage.event_queue import allocate_generation
from sns_recommend.storage.postgres import connection


def baseline(user_id: int, strategy: str = "latest") -> dict[str, str | int]:
    if strategy not in {"latest", "popular"}:
        raise ValueError("unsupported baseline")
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    ids = source.ordered_post_ids(strategy)
    with connection() as conn:
        generation = allocate_generation(conn, user_id)
        publish(user_id, ids, strategy, generation)
    return {"user_id": user_id, "strategy": strategy, "count": len(ids)}
