from . import source
from .db import connection
from .feed import publish
from .event_queue import allocate_generation


def baseline(user_id, strategy="latest"):
    if strategy not in {"latest", "popular"}:
        raise ValueError("unsupported baseline")
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    ids = source.ordered_post_ids(strategy)
    with connection() as conn:
        generation = allocate_generation(conn, user_id)
    publish(user_id, ids, strategy, generation)
    return {"user_id": user_id, "strategy": strategy, "count": len(ids)}
