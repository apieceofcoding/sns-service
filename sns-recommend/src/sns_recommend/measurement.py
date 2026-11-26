from __future__ import annotations

from .db import connection


def record_served(user_id: int, feed: dict) -> None:
    keys = ("strategy", "model_version", "experiment", "arm")
    with connection() as conn:
        conn.cursor().executemany(
            """INSERT INTO served_posts(user_id,post_id,strategy,model_version,experiment,arm)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (user_id,post_id) DO UPDATE SET
            strategy=EXCLUDED.strategy,model_version=EXCLUDED.model_version,
            experiment=EXCLUDED.experiment,arm=EXCLUDED.arm,served_at=now()""",
            [(user_id, post_id, *(feed[k] for k in keys)) for post_id in feed["post_ids"]],
        )
