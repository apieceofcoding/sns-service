from __future__ import annotations

from datetime import UTC, datetime

from .db import source_connection
from .seed import advance_identity


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
