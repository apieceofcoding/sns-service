from __future__ import annotations

import time

from .experiment import assigned
from .feed import publish
from .profiles import build_user_vector
from .ranking import diversify, rank
from .retrieval import retrieve_candidates


def generate(user_id: int) -> dict:
    started = time.time()
    candidates = retrieve_candidates(user_id, user_vector=build_user_vector(user_id))
    group = assigned(user_id) or {}
    ranked = rank(user_id, candidates, group.get("model"))
    ranked["ids"] = diversify(candidates, ranked["ids"])
    ranked |= {"experiment": group.get("experiment"), "arm": group.get("arm")}
    published = publish(user_id, created_at=started, **ranked)
    return {"user_id": user_id, **ranked, "published": published}
