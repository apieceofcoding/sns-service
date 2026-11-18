"""What the worker did: how long each run took and which ranking it served."""

from __future__ import annotations

from .db import connection


def record_generation(event: dict, duration_ms: float, result: dict | None, error: str = ""):
    result = result or {}
    with connection() as conn:
        conn.execute(
            """INSERT INTO generation_runs(event_id,user_id,strategy,model_version,duration_ms,
            published,error) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET
            strategy=EXCLUDED.strategy,model_version=EXCLUDED.model_version,
            duration_ms=EXCLUDED.duration_ms,published=EXCLUDED.published,error=EXCLUDED.error""",
            (
                event["id"],
                event["user_id"],
                result.get("strategy"),
                result.get("model_version"),
                duration_ms,
                result.get("published"),
                error or None,
            ),
        )


def record_served(user_id: int, feed: dict) -> None:
    """What this page showed: the list, each position, and the ranking that produced it.

    Later reactions are joined to these rows, so a click can be traced to a model version and
    an experiment group. A post served again before it was seen keeps the latest record.
    """
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


def metrics(minutes: int = 60) -> dict:
    with connection() as conn:
        runs = conn.execute(
            """SELECT count(*) AS runs,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,
            count(*) FILTER (WHERE strategy='model') AS model,
            count(*) FILTER (WHERE strategy='explore') AS explore,
            count(*) FILTER (WHERE strategy LIKE 'embedding%%') AS fallback,
            count(*) FILTER (WHERE error IS NOT NULL) AS errors
            FROM generation_runs WHERE created_at>now()-make_interval(mins=>%s)""",
            (minutes,),
        ).fetchone()
        serving = conn.execute(
            "SELECT id,activated_at FROM model_versions WHERE status='active'"
        ).fetchone()
        experiment = conn.execute(
            """SELECT name,control_model,treatment_model,started_at FROM experiments
            WHERE stopped_at IS NULL"""
        ).fetchone()
    return {
        "window_minutes": minutes,
        "generation": runs,
        "active_model": serving,
        "experiment": experiment,
    }
