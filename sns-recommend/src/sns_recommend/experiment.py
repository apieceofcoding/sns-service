"""A/B test: half the readers get the embedding order (control), half the model (treatment).

Offline NDCG says which ranking orders past impressions better. Only readers reacting to the
feed we actually served can say whether the feed got better.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime, timedelta
from random import Random

from . import simulator, source
from .db import connection
from .event_worker import drain
from .events import excluded_ids
from .feed import read_feed
from .registry import active

ARMS = ("control", "treatment")


def arm(user_id: int, name: str) -> str:
    """Stable per experiment: the same reader always lands in the same group."""
    digest = hashlib.sha256(f"{name}:{user_id}".encode()).digest()
    return ARMS[digest[0] % 2]


def running() -> dict | None:
    with connection() as conn:
        return conn.execute(
            "SELECT name,started_at FROM experiments WHERE stopped_at IS NULL"
        ).fetchone()


def assigned(user_id: int) -> str | None:
    current = running()
    return arm(user_id, current["name"]) if current else None


def start(name: str) -> dict:
    if running():
        raise ValueError("another experiment is running")
    if active() is None:
        raise LookupError("promote a model first; without one both groups get the same order")
    with connection() as conn:
        return conn.execute(
            "INSERT INTO experiments(name) VALUES (%s) RETURNING name,started_at", (name,)
        ).fetchone()


def stop() -> dict:
    with connection() as conn:
        row = conn.execute(
            """UPDATE experiments SET stopped_at=now() WHERE stopped_at IS NULL
            RETURNING name,started_at,stopped_at"""
        ).fetchone()
    if row is None:
        raise LookupError("no running experiment")
    return row


def simulate_feed(rounds: int = 3, users: int = 300, shift: bool = False) -> dict:
    """Each round every reader opens the feed we published, sees the top posts and reacts."""
    from .generation import generate_for_user  # generation asks this module for the group

    current = running()
    if current is None:
        raise LookupError("start an experiment first")
    rnd = Random(f"feed:{datetime.now(UTC):%Y%m%d%H%M}")
    reader_ids = simulator.readers(users)
    tastes = {u: simulator.taste(u, shift) for u in reader_ids}
    moods = {u: max(t, key=t.get) for u, t in tastes.items()}
    posts = {p["id"]: p for p in simulator.visible_posts()}
    shown = 0
    for _ in range(rounds):
        drain()  # Earlier reactions become history and the seen set before the next feed.
        rows: tuple[list, list, list] = ([], [], [])
        for user_id in reader_ids:
            try:
                generate_for_user(user_id)
            except (LookupError, RuntimeError):
                continue  # Unknown reader, or a running worker already owns the request.
            ids = read_feed(
                user_id, simulator.SHOWN, excluded=excluded_ids(user_id), alive=source.alive_ids
            )["post_ids"]
            moods[user_id] = simulator.drift(rnd, tastes[user_id], moods[user_id])
            # Backdate so reactions (up to 20 seconds later) are not in the future,
            # but never before the experiment started.
            at = max(current["started_at"], datetime.now(UTC) - timedelta(seconds=30))
            feed = [posts[i] for i in ids if i in posts]
            simulator.visit(rnd, user_id, feed, at, tastes[user_id], moods[user_id], rows)
        simulator.write(*rows)
        shown += len(rows[0])
    drain()
    return {"rounds": rounds, "impressions": shown, **report()}


def compare_rates(clicks_a: int, shown_a: int, clicks_b: int, shown_b: int) -> dict:
    """Two-proportion z-test. A small p-value means the gap is unlikely to be luck."""
    if not shown_a or not shown_b:
        return {"lift": None, "p_value": None}
    rate_a, rate_b = clicks_a / shown_a, clicks_b / shown_b
    pooled = (clicks_a + clicks_b) / (shown_a + shown_b)
    spread = math.sqrt(pooled * (1 - pooled) * (1 / shown_a + 1 / shown_b))
    p_value = math.erfc(abs(rate_b - rate_a) / spread / math.sqrt(2)) if spread else 1.0
    lift = round(rate_b / rate_a - 1, 3) if rate_a else None
    return {"lift": lift, "p_value": round(p_value, 4)}


def report(name: str | None = None) -> dict:
    """Click and like rates per group, counted from events inside the experiment window."""
    with connection() as conn:
        exp = conn.execute(
            """SELECT name,started_at,stopped_at FROM experiments
            WHERE %s::text IS NULL OR name=%s ORDER BY started_at DESC LIMIT 1""",
            (name, name),
        ).fetchone()
        if exp is None:
            raise LookupError("no experiment")
        rows = conn.execute(
            """SELECT user_id,action,count(*) AS n FROM user_events
            WHERE action IN ('impression','click','like') AND removed_at IS NULL
            AND occurred_at>=%s AND (%s::timestamptz IS NULL OR occurred_at<%s)
            GROUP BY user_id,action""",
            (exp["started_at"], exp["stopped_at"], exp["stopped_at"]),
        ).fetchall()
    groups = {a: {"readers": set(), "impression": 0, "click": 0, "like": 0} for a in ARMS}
    for row in rows:
        group = groups[arm(row["user_id"], exp["name"])]
        group["readers"].add(row["user_id"])
        group[row["action"]] += row["n"]
    arms = {
        a: {
            "readers": len(g["readers"]),
            "impressions": g["impression"],
            "click_rate": round(g["click"] / g["impression"], 4) if g["impression"] else None,
            "like_rate": round(g["like"] / g["impression"], 4) if g["impression"] else None,
        }
        for a, g in groups.items()
    }
    control, treatment = groups["control"], groups["treatment"]
    clicks = compare_rates(
        control["click"], control["impression"], treatment["click"], treatment["impression"]
    )
    return {"experiment": exp["name"], "arms": arms, "click_rate": clicks}
