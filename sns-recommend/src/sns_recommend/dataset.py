"""Training examples from logged impressions. Training and serving share these features."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import torch

from . import source
from .db import connection
from .embeddings import embedding_model

HISTORY = 20
CANDIDATES = 30
SESSION_GAP = timedelta(minutes=5)
POSITIVE = ("click", "like", "reply", "repost")
ACTIONS = {action: i + 1 for i, action in enumerate(POSITIVE)}
LABELS = ("click", "like")


def load_events(until: datetime | None = None) -> list[dict]:
    with connection() as conn:
        return conn.execute(
            """SELECT user_id,post_id,action,occurred_at FROM user_events
            WHERE action=ANY(%s) AND removed_at IS NULL
            AND (%s::timestamptz IS NULL OR occurred_at<=%s)
            ORDER BY user_id,occurred_at,post_id""",
            (["impression", *POSITIVE], until, until),
        ).fetchall()


def build_sessions(events: list[dict]) -> list[dict]:
    """Group a user's impressions into visits. Labels are reactions to the shown posts."""
    sessions: list[dict] = []
    by_user: dict[int, list[dict]] = {}
    for event in events:
        by_user.setdefault(event["user_id"], []).append(event)
    for user_id, rows in by_user.items():
        reactions: dict[int, set[str]] = {}
        for row in rows:
            if row["action"] in POSITIVE:
                reactions.setdefault(row["post_id"], set()).add(row["action"])
        current: dict | None = None
        for row in rows:
            if row["action"] != "impression":
                continue
            if current is None or row["occurred_at"] - current["last"] > SESSION_GAP:
                history = [
                    (r["post_id"], r["action"], r["occurred_at"])
                    for r in rows
                    if r["action"] in POSITIVE and r["occurred_at"] < row["occurred_at"]
                ][-HISTORY:]
                current = {"user_id": user_id, "start": row["occurred_at"], "history": history}
                current["candidates"], current["labels"] = [], []
                sessions.append(current)
            current["last"] = row["occurred_at"]
            if len(current["candidates"]) < CANDIDATES:
                done = reactions.get(row["post_id"], set())
                current["candidates"].append(row["post_id"])
                current["labels"].append([float(label in done) for label in LABELS])
    return sorted(sessions, key=lambda s: s["start"])


def post_features(post_ids) -> dict[int, dict]:
    """Current vector and creation time per post. Posts without a current vector are skipped."""
    ids = sorted(set(post_ids))
    with connection() as conn:
        rows = conn.execute(
            """SELECT post_id,content_version,embedding::text FROM post_embeddings
            WHERE post_id=ANY(%s) AND model=%s""",
            (ids, embedding_model()),
        ).fetchall()
    created = source.created_times(ids)
    return {
        r["post_id"]: {"vector": json.loads(r["embedding"]), "created_at": created[r["post_id"]][1]}
        for r in rows
        if r["post_id"] in created and created[r["post_id"]][0] == r["content_version"]
    }


def encode(sessions: list[dict], features: dict[int, dict]) -> dict[str, torch.Tensor]:
    """Turn sessions into padded tensors. Ages are in hours from the session start."""
    ids = sorted(features)
    index = {post_id: i + 1 for i, post_id in enumerate(ids)}  # 0 is padding
    dims = len(features[ids[0]]["vector"]) if ids else 1
    table = torch.zeros(len(ids) + 1, dims)
    for post_id, i in index.items():
        table[i] = torch.tensor(features[post_id]["vector"])
    n = len(sessions)
    batch = {
        "table": table,
        "history": torch.zeros(n, HISTORY, dtype=torch.long),
        "actions": torch.zeros(n, HISTORY, dtype=torch.long),
        "history_age": torch.zeros(n, HISTORY),
        "candidates": torch.zeros(n, CANDIDATES, dtype=torch.long),
        "candidate_age": torch.zeros(n, CANDIDATES),
        "labels": torch.zeros(n, CANDIDATES, len(LABELS)),
    }
    for row, session in enumerate(sessions):
        history = [h for h in session["history"] if h[0] in index][-HISTORY:]
        offset = HISTORY - len(history)  # most recent action is always last
        for j, (post_id, action, at) in enumerate(history):
            batch["history"][row, offset + j] = index[post_id]
            batch["actions"][row, offset + j] = ACTIONS[action]
            batch["history_age"][row, offset + j] = hours(session["start"] - at)
        kept = [(c, y) for c, y in zip(session["candidates"], session["labels"]) if c in index]
        for j, (post_id, label) in enumerate(kept[:CANDIDATES]):
            batch["candidates"][row, j] = index[post_id]
            batch["candidate_age"][row, j] = hours(
                session["start"] - features[post_id]["created_at"]
            )
            batch["labels"][row, j] = torch.tensor(label)
    return batch


def hours(delta: timedelta) -> float:
    return max(0.0, delta.total_seconds() / 3600)
