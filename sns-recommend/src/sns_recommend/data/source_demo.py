from __future__ import annotations

from datetime import UTC, datetime

from sns_recommend.data.seed import advance_identity
from sns_recommend.storage.postgres import source_connection


def change_post(post_id: int, body: str, author_id: int = 1) -> dict[str, int]:
    now = datetime.now(UTC)
    with source_connection() as conn:
        row = conn.execute(
            """INSERT INTO posts(id,content,user_id,like_count,repost_count,reply_count,
            view_count,created_at,modified_at)
            VALUES (%s,%s,%s,0,0,0,0,%s,%s) ON CONFLICT(id) DO UPDATE SET
            content=EXCLUDED.content,modified_at=EXCLUDED.modified_at RETURNING content_version""",
            (post_id, body, author_id, now, now),
        ).fetchone()
        advance_identity(conn, "posts")
    return {"post_id": post_id, "version": row["content_version"]}


def seed_actions() -> dict[str, int]:
    """Add synthetic likes to the SNS database. The event worker copies them like any other."""
    count = 0
    now = datetime.now(UTC)
    with source_connection() as conn:
        for user_id, posts in {7: [1, 4], 8: [2, 5], 9: [3, 6]}.items():
            for post_id in posts:
                row = conn.execute(
                    """INSERT INTO likes(user_id,post_id,created_at,modified_at)
                    SELECT %s,%s,%s,%s WHERE NOT EXISTS (
                        SELECT 1 FROM likes WHERE user_id=%s AND post_id=%s AND deleted_at IS NULL
                    ) RETURNING id""",
                    (user_id, post_id, now, now, user_id, post_id),
                ).fetchone()
                count += bool(row)
    return {"actions": count}
