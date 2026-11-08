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


def metrics(minutes: int = 60) -> dict:
    with connection() as conn:
        runs = conn.execute(
            """SELECT count(*) AS runs,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,
            count(*) FILTER (WHERE strategy='model') AS model,
            count(*) FILTER (WHERE strategy LIKE 'embedding%%') AS fallback,
            count(*) FILTER (WHERE error IS NOT NULL) AS errors
            FROM generation_runs WHERE created_at>now()-make_interval(mins=>%s)""",
            (minutes,),
        ).fetchone()
        serving = conn.execute(
            "SELECT id,activated_at FROM model_versions WHERE status='active'"
        ).fetchone()
    return {"window_minutes": minutes, "generation": runs, "active_model": serving}
