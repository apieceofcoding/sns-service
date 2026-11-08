"""Rank candidates with the trained model, check the output, then spread authors out."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from .dataset import HISTORY, LABELS, POSITIVE, encode, post_features
from .db import connection
from .model import score
from .model_store import active_model


def recent_history(user_id: int) -> list[tuple[int, str, datetime]]:
    """The same history the model was trained on: the last reactions, oldest first."""
    with connection() as conn:
        rows = conn.execute(
            """SELECT post_id,action,occurred_at FROM user_events WHERE user_id=%s
            AND action=ANY(%s) AND removed_at IS NULL ORDER BY occurred_at DESC LIMIT %s""",
            (user_id, list(POSITIVE), HISTORY),
        ).fetchall()
    return [(r["post_id"], r["action"], r["occurred_at"]) for r in reversed(rows)]


def rank(user_id: int, candidates: list[dict]) -> dict:
    """Order by predicted reactions. Without a usable model, keep the retrieval order."""
    retrieval_order = [c["id"] for c in candidates]
    model, version = active_model()
    if model is None or not candidates:
        return {"ids": retrieval_order, "scores": None, "strategy": "embedding"}
    history = recent_history(user_id)
    features = post_features(retrieval_order + [h[0] for h in history])
    scored = [i for i in retrieval_order if i in features]
    session = {
        "start": datetime.now(UTC),
        "history": history,
        "candidates": scored,
        "labels": [[0.0] * len(LABELS)] * len(scored),
    }
    values = score(model, encode([session], features))[0][: len(scored)].tolist() if scored else []
    if len(values) != len(scored) or not all(math.isfinite(v) for v in values):
        return {"ids": retrieval_order, "scores": None, "strategy": "embedding_fallback"}
    scores = dict(zip(scored, values, strict=True))
    # Posts without a current vector cannot be scored yet; they follow in retrieval order.
    ids = sorted(scored, key=lambda i: -scores[i]) + [i for i in retrieval_order if i not in scores]
    return {"ids": ids, "scores": scores, "strategy": "model", "model_version": version}


def diversify(candidates: list[dict], ids: list[int], decay: float = 0.7) -> list[int]:
    """Each earlier post by the same author lowers a post's priority by `decay`."""
    author = {c["id"]: c["author_id"] for c in candidates}
    priority = {post_id: 1 / (rank + 1) for rank, post_id in enumerate(ids)}
    shown: dict[int, int] = {}
    result, remaining = [], list(ids)
    while remaining:
        best = max(remaining, key=lambda i: priority[i] * decay ** shown.get(author[i], 0))
        result.append(best)
        remaining.remove(best)
        shown[author[best]] = shown.get(author[best], 0) + 1
    return result
