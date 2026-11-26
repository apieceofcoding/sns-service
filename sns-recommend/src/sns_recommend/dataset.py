from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import torch

from . import source
from .db import connection
from .embeddings import embedding_model

HISTORY = 20
CANDIDATES = 30
SESSION_GAP = timedelta(minutes=5)
LABEL_WINDOW = timedelta(minutes=5)
POSITIVE = ("click", "like", "reply", "repost")
ACTIONS = {action: i + 1 for i, action in enumerate(POSITIVE)}
LABELS = ("click", "like")


def load_events() -> list[dict]:
    with connection() as conn:
        return conn.execute(
            """SELECT user_id,post_id,action,occurred_at FROM user_events
            WHERE action=ANY(%s) AND deleted_at IS NULL
            ORDER BY user_id,occurred_at,post_id""",
            (["impression", *POSITIVE],),
        ).fetchall()


def history_before(events: list[dict], at: datetime) -> list[tuple[int, str, datetime]]:
    return [
        (e["post_id"], e["action"], e["occurred_at"])
        for e in events
        if e["action"] in POSITIVE and e["occurred_at"] < at
    ][-HISTORY:]


def build_sessions(events: list[dict], now: datetime | None = None) -> list[dict]:
    closed = (now or datetime.now(UTC)) - LABEL_WINDOW
    by_user: dict[int, list[dict]] = {}
    for event in events:
        by_user.setdefault(event["user_id"], []).append(event)
    sessions: list[dict] = []
    for user_id, rows in by_user.items():
        reactions: dict[int, list[dict]] = {}
        for row in rows:
            if row["action"] in POSITIVE:
                reactions.setdefault(row["post_id"], []).append(row)
        session: dict | None = None
        for row in rows:
            shown_at = row["occurred_at"]
            if row["action"] != "impression" or shown_at > closed:
                continue
            if session is None or shown_at - session["last"] > SESSION_GAP:
                history = history_before(rows, shown_at)
                session = {"user_id": user_id, "start": shown_at, "history": history}
                session["candidates"], session["labels"] = [], []
                sessions.append(session)
            session["last"] = shown_at
            if len(session["candidates"]) < CANDIDATES:
                done = {
                    r["action"]
                    for r in reactions.get(row["post_id"], ())
                    if shown_at <= r["occurred_at"] <= shown_at + LABEL_WINDOW
                }
                session["candidates"].append(row["post_id"])
                session["labels"].append([float(label in done) for label in LABELS])
    return sorted(sessions, key=lambda s: s["start"])


def post_features(post_ids) -> dict[int, dict]:
    ids = sorted(set(post_ids))
    with connection() as conn:
        rows = conn.execute(
            "SELECT post_id,embedding::text FROM post_embeddings WHERE post_id=ANY(%s) AND model=%s",
            (ids, embedding_model()),
        ).fetchall()
    created = source.created_times(ids)
    return {
        r["post_id"]: {"vector": json.loads(r["embedding"]), "created_at": created[r["post_id"]]}
        for r in rows
        if r["post_id"] in created
    }


def encode(sessions: list[dict], features: dict[int, dict]) -> dict[str, torch.Tensor]:
    index = {post_id: i + 1 for i, post_id in enumerate(sorted(features))}
    vectors = [features[post_id]["vector"] for post_id in index]
    table = torch.tensor([[0.0] * len(vectors[0]), *vectors]) if vectors else torch.zeros(1, 1)
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
        for j, (post_id, action, at) in enumerate(history, HISTORY - len(history)):
            batch["history"][row, j] = index[post_id]
            batch["actions"][row, j] = ACTIONS[action]
            batch["history_age"][row, j] = days(session["start"] - at)
        shown = zip(session["candidates"], session["labels"], strict=True)
        for j, (post_id, label) in enumerate([s for s in shown if s[0] in index][:CANDIDATES]):
            batch["candidates"][row, j] = index[post_id]
            batch["candidate_age"][row, j] = days(
                session["start"] - features[post_id]["created_at"]
            )
            batch["labels"][row, j] = torch.tensor(label)
    return batch


def days(delta: timedelta) -> float:
    return max(0.0, delta.total_seconds() / 86400)
