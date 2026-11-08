"""One recommendation run: retrieve, rank, filter and spread, then publish."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from .db import connection
from .event_queue import allocate_generation, claim, enqueue, finish, heartbeat
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
    ranked = rank(user_id, candidates)
    ids = diversify(candidates, ranked["ids"])
    published = publish_if_owner(event, ids, ranked, generation, created_at)
    if not finish(event):
        raise RuntimeError("event lease lost")
    return {
        "user_id": user_id,
        "strategy": ranked["strategy"],
        "model_version": ranked.get("model_version"),
        "post_ids": ids,
        "published": published,
    }


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
        )


def generate_for_user(user_id: int) -> dict:
    event = claim(event_id=enqueue(user_id))
    if event is None:
        raise RuntimeError("request already owned by a worker")
    with heartbeat(event):
        return generate(event)
