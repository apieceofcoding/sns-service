from __future__ import annotations

import random
import time

from .config import settings
from .experiment import assigned
from .feed import publish
from .measurement import measured
from .profiles import build_user_vector
from .ranking import diversify, rank
from .retrieval import retrieve_candidates


@measured
def generate(user_id: int) -> dict:
    # A list that started later wins in Redis, so two runs for one user cannot go backwards.
    started = time.time()
    candidates = retrieve_candidates(user_id, user_vector=build_user_vector(user_id))
    ranked = order(user_id, candidates)
    published = publish(
        user_id,
        ranked["ids"],
        ranked["strategy"],
        int(started * 1_000_000),
        created_at=started,
        model_version=ranked.get("model_version"),
        experiment=ranked.get("experiment"),
        arm=ranked.get("arm"),
    )
    return {
        "user_id": user_id,
        "strategy": ranked["strategy"],
        "model_version": ranked.get("model_version"),
        "arm": ranked.get("arm"),
        "post_ids": ranked["ids"],
        "published": published,
    }


def order(user_id: int, candidates: list[dict]) -> dict:
    retrieval_order = [c["id"] for c in candidates]
    if random.random() < settings().explore_rate:
        return {"ids": random.sample(retrieval_order, len(retrieval_order)), "strategy": "explore"}
    group = assigned(user_id) or {"model": None, "spread": True}
    if "arm" in group and group["model"] is None:
        ranked = {"ids": retrieval_order, "strategy": "embedding"}
    else:
        ranked = rank(user_id, candidates, group["model"])
    if group["spread"]:
        ranked["ids"] = diversify(candidates, ranked["ids"])
    return {**ranked, "experiment": group.get("experiment"), "arm": group.get("arm")}
