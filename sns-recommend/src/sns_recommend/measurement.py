from __future__ import annotations

from .db import connection


def record_served(user_id: int, feed: dict) -> None:
    rows = [
        (
            user_id,
            post_id,
            feed["snapshot_id"],
            position,
            feed["strategy"],
            feed["model_version"],
            feed["experiment"],
            feed["arm"],
        )
        for post_id, position in zip(feed["post_ids"], feed.get("positions", ()), strict=False)
    ]
    with connection() as conn:
        conn.cursor().executemany(
            """INSERT INTO served_posts(user_id,post_id,snapshot_id,position,strategy,
            model_version,experiment,arm) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id,post_id) DO UPDATE SET snapshot_id=EXCLUDED.snapshot_id,
            position=EXCLUDED.position,strategy=EXCLUDED.strategy,
            model_version=EXCLUDED.model_version,experiment=EXCLUDED.experiment,
            arm=EXCLUDED.arm,served_at=now()""",
            rows,
        )


def metrics() -> dict:
    with connection() as conn:
        serving = conn.execute(
            "SELECT id,activated_at FROM model_versions WHERE status='active'"
        ).fetchone()
        experiment = conn.execute(
            """SELECT name,control_model,treatment_model,started_at FROM experiments
            WHERE stopped_at IS NULL"""
        ).fetchone()
        served = conn.execute(
            """SELECT strategy,count(*) AS posts FROM served_posts
            WHERE served_at>now()-interval '1 hour' GROUP BY strategy"""
        ).fetchall()
    return {
        "active_model": serving,
        "experiment": experiment,
        "served_last_hour": {row["strategy"]: row["posts"] for row in served},
    }
