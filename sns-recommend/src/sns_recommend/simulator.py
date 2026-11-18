"""Synthetic readers for training data. Each reader has a hidden taste that the model must learn.

The simulator writes to the SNS database like the app would: impressions and clicks go to
post_actions, likes go to likes. The event worker copies them into user_events as usual.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from random import Random
from uuid import uuid4

from .db import connection, source_connection
from .seed import AUTHORS, TOPICS, advance_identity, post_fields, topic_of
from .source import VISIBLE

READERS = {7: ("backend", "ai_dev"), 8: ("travel", "travel_video"), 9: ("fitness", "fitness_food")}
FIRST_SIMULATED_USER = 101
SLOT = timedelta(minutes=6)
SHOWN = 10


def readers(users: int = 300) -> list[int]:
    return list(READERS) + list(range(FIRST_SIMULATED_USER, FIRST_SIMULATED_USER + users))


def age_cost(shift: bool = False) -> float:
    """What an hour of post age costs a reader. Each shift flips between two moods of the
    whole service: ordinary days, and a rush where only fresh posts get attention.

    Stored so every command sees the same readers."""
    with connection() as conn:
        row = conn.execute(
            """INSERT INTO simulation(shifts) VALUES (%s) ON CONFLICT (only_row)
            DO UPDATE SET shifts=simulation.shifts+%s RETURNING shifts""",
            (int(shift), int(shift)),
        ).fetchone()
    return 0.5 if row["shifts"] % 2 else 0.05


def taste(user_id: int) -> dict[str, float]:
    """Hidden preference: a main topic and a second topic."""
    first, second = READERS.get(user_id) or Random(user_id * 7919).sample(TOPICS, 2)
    return {t: 1.0 if t == first else 0.6 if t == second else 0.0 for t in TOPICS}


def drift(rnd: Random, weights: dict[str, float], mood: str) -> str:
    """Short-term interest moves between visits, mostly toward the hidden taste."""
    if rnd.random() < 0.4:
        return rnd.choices(TOPICS, [weights[t] + 0.1 for t in TOPICS])[0]
    return mood


def react(rnd: Random, weight: float, in_mood: bool, aging: float) -> tuple[bool, bool]:
    logit = -3 + 2.5 * weight + 1.8 * in_mood - aging
    click = rnd.random() < 1 / (1 + math.exp(-logit))
    like = click and rnd.random() < 1 / (1 + math.exp(1 - 1.5 * weight))
    return click, like


def visit(rnd, user_id, posts, at, weights, mood, hourly_cost, rows) -> None:
    """The reader sees `posts` at `at` and reacts. Appends to (impressions, clicks, likes)."""
    impressions, actions, likes = rows
    for post in posts:
        topic = topic_of(post["user_id"])
        aging = hourly_cost * (at - post["created_at"]).total_seconds() / 3600
        click, like = react(rnd, weights[topic], topic == mood, aging)
        impressions.append((uuid4(), user_id, post["id"], "impression", at))
        if click:
            actions.append((uuid4(), user_id, post["id"], "click", at + timedelta(seconds=5)))
        if like:
            likes.append((user_id, post["id"], at + timedelta(seconds=20), datetime.now(UTC)))


def visible_posts() -> list[dict]:
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,user_id,created_at AT TIME ZONE 'UTC' AS created_at FROM posts
            WHERE {VISIBLE} AND user_id=ANY(%s)""",
            (list(AUTHORS),),
        ).fetchall()


def write(impressions: list, actions: list, likes: list) -> None:
    """Write like the app does: impressions and clicks to post_actions, likes to likes."""
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


def publish_posts(count: int) -> int:
    """Authors write `count` new posts now, continuing the seed's author and body pattern."""
    now = datetime.now(UTC)
    with source_connection() as conn:
        first = conn.execute("SELECT max(id)+1 AS next FROM posts").fetchone()["next"]
        for post_id in range(first, first + count):
            author_id, body = post_fields(post_id)
            conn.execute(
                """INSERT INTO posts(id,user_id,content,like_count,repost_count,reply_count,
                view_count,created_at,modified_at) VALUES (%s,%s,%s,0,0,0,0,%s,%s)""",
                (post_id, author_id, body, now, now),
            )
        advance_identity(conn, "posts")
    return count


def simulate(users: int = 300, sessions: int = 15, hours: float = 4, shift: bool = False):
    """Readers see random recent posts in past time slots. Used to collect training data."""
    now = datetime.now(UTC)
    start = now - timedelta(hours=hours)
    reader_ids = readers(users)
    hourly_cost = age_cost(shift)
    rnd = Random(f"{now:%Y%m%d%H}:{hourly_cost}")
    rows: tuple[list, list, list] = ([], [], [])
    with source_connection() as conn:
        for user_id in reader_ids[len(READERS) :]:
            conn.execute(
                """INSERT INTO users(id,username,created_at,modified_at)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (user_id, f"reader_{user_id}", now, now),
            )
        advance_identity(conn, "users")
        seen_rows = conn.execute(
            "SELECT user_id,post_id FROM post_actions WHERE action='impression'"
        ).fetchall()
    posts = visible_posts()
    seen = {(r["user_id"], r["post_id"]) for r in seen_rows}
    slots = max(1, int((now - start) / SLOT))
    for user_id in reader_ids:
        weights = taste(user_id)
        mood = max(weights, key=weights.get)
        for slot in sorted(rnd.sample(range(slots), min(sessions, slots))):
            at = start + slot * SLOT + timedelta(seconds=rnd.uniform(0, 60))
            mood = drift(rnd, weights, mood)
            available = [
                p
                for p in posts
                if p["created_at"] < at
                and at - p["created_at"] < timedelta(hours=48)
                and (user_id, p["id"]) not in seen
            ]
            shown = rnd.sample(available, min(SHOWN, len(available)))
            seen.update((user_id, p["id"]) for p in shown)
            visit(rnd, user_id, shown, at, weights, mood, hourly_cost, rows)
    write(*rows)
    impressions, actions, likes = rows
    return {
        "readers": len(reader_ids),
        "impressions": len(impressions),
        "clicks": len(actions),
        "likes": len(likes),
        "click_rate": round(len(actions) / max(1, len(impressions)), 3),
        "age_cost_per_hour": hourly_cost,
    }
