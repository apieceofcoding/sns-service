"""Model versions: every trained model is recorded, and exactly one serves at a time."""

from __future__ import annotations

import json

from .db import connection


def register(path: str, report: dict, status: str = "candidate") -> int:
    with connection() as conn:
        row = conn.execute(
            """INSERT INTO model_versions(status,path,embedding_model,trained_until,sessions,metrics)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                status,
                path,
                report["embedding_model"],
                report["trained_until"],
                report["sessions"]["train"],
                json.dumps(report),
            ),
        ).fetchone()
    return row["id"]


def active() -> dict | None:
    with connection() as conn:
        return conn.execute("SELECT * FROM model_versions WHERE status='active'").fetchone()


def promote(version: int) -> dict:
    """Serve this version. The previous one is retired and stays available for rollback."""
    with connection() as conn:
        conn.execute("LOCK TABLE model_versions IN SHARE ROW EXCLUSIVE MODE")
        row = conn.execute("SELECT status FROM model_versions WHERE id=%s", (version,)).fetchone()
        if row is None or row["status"] == "rejected":
            raise ValueError("only a trained, accepted version can serve")
        conn.execute("UPDATE model_versions SET status='retired' WHERE status='active'")
        conn.execute(
            "UPDATE model_versions SET status='active',activated_at=now() WHERE id=%s", (version,)
        )
    return {"active": version}


def rollback() -> dict:
    """Go back to the version that served before the current one."""
    with connection() as conn:
        row = conn.execute(
            """SELECT id FROM model_versions WHERE status='retired' AND activated_at IS NOT NULL
            ORDER BY activated_at DESC LIMIT 1"""
        ).fetchone()
    if row is None:
        raise LookupError("no earlier version to roll back to")
    return promote(row["id"])


def versions(limit: int = 10) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT id,status,trained_until,sessions,metrics->'ndcg@10' AS ndcg,
            created_at,activated_at FROM model_versions ORDER BY id DESC LIMIT %s""",
            (limit,),
        ).fetchall()
    return rows
