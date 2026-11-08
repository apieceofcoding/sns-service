"""Synthetic readers for training data. Each reader has a hidden taste that the model must learn.

The simulator writes to the SNS database like the app would: impressions and clicks go to
post_actions, likes go to likes. The event worker copies them into user_events as usual.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from random import Random
from uuid import uuid4

from .db import source_connection
from .seed import TOPICS, advance_identity
from .source import VISIBLE

READERS = {7: ("backend", "ai_dev"), 8: ("travel", "travel_video"), 9: ("fitness", "fitness_food")}
FIRST_SIMULATED_USER = 101
SLOT = timedelta(minutes=6)
SHOWN = 10


def taste(user_id: int, shift: bool) -> dict[str, float]:
    """Hidden preference: a main topic and a second topic. Shift gives everyone a new taste."""
    if user_id in READERS and not shift:
        first, second = READERS[user_id]
    else:
        first, second = Random(user_id * 7919 + shift).sample(TOPICS, 2)
    return {t: 1.0 if t == first else 0.6 if t == second else 0.0 for t in TOPICS}


def react(rnd: Random, weight: float, in_mood: bool, age_hours: float) -> tuple[bool, bool]:
    logit = -3 + 2.5 * weight + 1.8 * in_mood - 0.25 * age_hours
    click = rnd.random() < 1 / (1 + math.exp(-logit))
    like = click and rnd.random() < 1 / (1 + math.exp(1 - 1.5 * weight))
    return click, like


def simulate(users: int = 300, sessions: int = 15, hours: float = 4, shift: bool = False):
    now = datetime.now(UTC)
    start = now - timedelta(hours=hours)
    reader_ids = list(READERS) + list(range(FIRST_SIMULATED_USER, FIRST_SIMULATED_USER + users))
    rnd = Random(f"{now:%Y%m%d%H}:{shift}")
    impressions, actions, likes = [], [], []
    with source_connection() as conn:
        for user_id in reader_ids[len(READERS) :]:
            conn.execute(
                """INSERT INTO users(id,username,created_at,modified_at)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (user_id, f"reader_{user_id}", now, now),
            )
        advance_identity(conn, "users")
        posts = conn.execute(
            f"""SELECT id,user_id,created_at AT TIME ZONE 'UTC' AS created_at FROM posts
            WHERE {VISIBLE} AND user_id BETWEEN 1 AND %s""",
            (len(TOPICS),),
        ).fetchall()
        seen_rows = conn.execute(
            "SELECT user_id,post_id FROM post_actions WHERE action='impression'"
        ).fetchall()
    seen = {(r["user_id"], r["post_id"]) for r in seen_rows}
    slots = max(1, int((now - start) / SLOT))
    for user_id in reader_ids:
        weights = taste(user_id, shift)
        mood = max(weights, key=weights.get)
        for slot in sorted(rnd.sample(range(slots), min(sessions, slots))):
            at = start + slot * SLOT + timedelta(seconds=rnd.uniform(0, 60))
            if rnd.random() < 0.4:  # Short-term interest drifts between visits.
                mood = rnd.choices(TOPICS, [weights[t] + 0.1 for t in TOPICS])[0]
            available = [
                p
                for p in posts
                if p["created_at"] < at
                and at - p["created_at"] < timedelta(hours=48)
                and (user_id, p["id"]) not in seen
            ]
            for post in rnd.sample(available, min(SHOWN, len(available))):
                seen.add((user_id, post["id"]))
                topic = TOPICS[post["user_id"] - 1]
                age = (at - post["created_at"]).total_seconds() / 3600
                click, like = react(rnd, weights[topic], topic == mood, age)
                impressions.append((uuid4(), user_id, post["id"], "impression", at))
                if click:
                    actions.append(
                        (uuid4(), user_id, post["id"], "click", at + timedelta(seconds=5))
                    )
                if like:
                    likes.append((user_id, post["id"], at + timedelta(seconds=20), now))
    with source_connection() as conn:
        with conn.cursor().copy(
            "COPY post_actions(event_id,user_id,post_id,action,created_at) FROM STDIN"
        ) as copy:
            for row in impressions + actions:
                copy.write_row(row)
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO likes(user_id,post_id,created_at,modified_at) VALUES (%s,%s,%s,%s)",
                likes,
            )
            cur.executemany(
                "UPDATE posts SET like_count=like_count+1 WHERE id=%s",
                [(post_id,) for _, post_id, _, _ in likes],
            )
    return {
        "readers": len(reader_ids),
        "impressions": len(impressions),
        "clicks": len(actions),
        "likes": len(likes),
        "click_rate": round(len(actions) / max(1, len(impressions)), 3),
        "shift": shift,
    }
