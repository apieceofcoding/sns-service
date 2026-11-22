from __future__ import annotations

import time

from .feed import publish
from .profiles import build_user_vector
from .ranking import diversify, rank
from .retrieval import retrieve_candidates


def generate(user_id: int) -> dict:
    started = time.time()
    candidates = retrieve_candidates(user_id, user_vector=build_user_vector(user_id))
    ranked = rank(user_id, candidates)
    ranked["ids"] = diversify(candidates, ranked["ids"])
    published = publish(
        user_id,
        ranked["ids"],
        ranked["strategy"],
        int(started * 1_000_000),
        created_at=started,
        model_version=ranked.get("model_version"),
    )
    return {
        "user_id": user_id,
        "strategy": ranked["strategy"],
        "model_version": ranked.get("model_version"),
        "post_ids": ranked["ids"],
        "published": published,
    }
