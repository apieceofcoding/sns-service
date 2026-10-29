from . import source
from .feed import publish


def baseline(user_id, strategy="latest"):
    if strategy not in {"latest", "popular"}:
        raise ValueError("unsupported baseline")
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    ids = source.ordered_post_ids(strategy)
    publish(user_id, ids, strategy)
    return {"user_id": user_id, "strategy": strategy, "count": len(ids)}
