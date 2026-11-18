"""One recommendation run: retrieve, rank, filter and spread, then publish."""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime

from .config import settings
from .db import connection
from .event_queue import allocate_generation, claim, enqueue, finish, heartbeat
from .experiment import assigned
from .feed import publish
from .measurement import record_generation
from .profiles import build_user_vector
from .ranking import diversify, rank
from .retrieval import retrieve_candidates


def generate(event: dict) -> dict:
    started = time.perf_counter()
    try:
        result = run(event)
    except Exception as exc:
        record_generation(event, (time.perf_counter() - started) * 1000, None, type(exc).__name__)
        raise
    record_generation(event, (time.perf_counter() - started) * 1000, result)
    return result


def run(event: dict) -> dict:
    user_id = event["user_id"]
    generation = allocate_generation()
    created_at = datetime.now(UTC).timestamp()
    candidates = retrieve_candidates(user_id, user_vector=build_user_vector(user_id))
    ranked = order(user_id, candidates)
    published = publish_if_owner(event, ranked["ids"], ranked, generation, created_at)
    if not finish(event):
        raise RuntimeError("event lease lost")
    return {
        "user_id": user_id,
        "strategy": ranked["strategy"],
        "model_version": ranked.get("model_version"),
        "arm": ranked.get("arm"),
        "post_ids": ranked["ids"],
        "published": published,
    }


def order(user_id: int, candidates: list[dict]) -> dict:
    """This feed's order: a shuffled explore feed, the reader's experiment group, or the default."""
    retrieval_order = [c["id"] for c in candidates]
    if random.random() < settings().explore_rate:
        # Readers react to posts no ranking chose, which keeps evaluation data unbiased.
        return {"ids": random.sample(retrieval_order, len(retrieval_order)), "strategy": "explore"}
    group = assigned(user_id) or {"model": None, "spread": True}
    if "arm" in group and group["model"] is None:
        ranked = {"ids": retrieval_order, "strategy": "embedding"}
    else:
        ranked = rank(user_id, candidates, group["model"])
    if group["spread"]:
        ranked["ids"] = diversify(candidates, ranked["ids"])
    return {**ranked, "experiment": group.get("experiment"), "arm": group.get("arm")}


def publish_if_owner(event, ids, ranked, generation, created_at) -> bool:
    """Publish only while this worker still owns the request."""
    with connection() as conn:
        row = conn.execute(
            "SELECT claim_id,processed_at,locked_until FROM user_events WHERE id=%s FOR UPDATE",
            (event["id"],),
        ).fetchone()
        if (
            row is None
            or row["claim_id"] != event["claim_id"]
            or row["processed_at"] is not None
            or row["locked_until"] <= datetime.now(UTC)
        ):
            return False
        return publish(
            event["user_id"],
            ids,
            ranked["strategy"],
            generation,
            str(event["id"]),
            created_at,
            ranked.get("model_version"),
            ranked.get("experiment"),
            ranked.get("arm"),
        )


def generate_for_user(user_id: int) -> dict:
    event = claim(event_id=enqueue(user_id))
    if event is None:
        raise RuntimeError("request already owned by a worker")
    with heartbeat(event):
        return generate(event)
