from __future__ import annotations

from datetime import UTC, datetime

from sns_recommend.data.seed import advance_identity
from sns_recommend.storage.postgres import source_connection


def change_post(post_id: int, body: str, author_id: int = 1) -> dict[str, str | int]:
    now = datetime.now(UTC)
    with source_connection() as conn:
        row = conn.execute(
            """INSERT INTO posts(id,content,user_id,created_at,modified_at)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET
            content=EXCLUDED.content,modified_at=EXCLUDED.modified_at RETURNING content_version""",
            (post_id, body, author_id, now, now),
        ).fetchone()
        advance_identity(conn, "posts")
        event = conn.execute(
            """SELECT id FROM recommend_events WHERE post_id=%s AND version=%s
            ORDER BY created_at DESC LIMIT 1""",
            (post_id, row["content_version"]),
        ).fetchone()
    return {"event_id": str(event["id"]), "version": row["content_version"]}


def seed_actions() -> dict[str, int]:
    from uuid import NAMESPACE_URL, uuid5

    count = 0
    with source_connection() as conn:
        for user_id, posts in {7: [1, 4], 8: [2, 5], 9: [3, 6]}.items():
            for post_id in posts:
                row = conn.execute(
                    """INSERT INTO recommend_events(id,action,user_id,post_id)
                    VALUES (%s,'like',%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
                    (
                        uuid5(NAMESPACE_URL, f"sns-course-like:{user_id}:{post_id}"),
                        user_id,
                        post_id,
                    ),
                ).fetchone()
                count += bool(row)
    return {"actions": count}
