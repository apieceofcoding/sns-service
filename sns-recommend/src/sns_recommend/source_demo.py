from __future__ import annotations

from datetime import UTC, datetime

from .db import source_connection
from .seed import advance_identity


def change_post(post_id: int, body: str, author_id: int = 1) -> dict[str,str | int]:
    now = datetime.now(UTC)
    with source_connection() as conn:
        row = conn.execute(
            """INSERT INTO posts(id,content,user_id,created_at,modified_at)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET
            content=EXCLUDED.content,modified_at=EXCLUDED.modified_at RETURNING content_version""",
            (post_id,body,author_id,now,now),
        ).fetchone()
        advance_identity(conn,"posts")
        event = conn.execute(
            """SELECT id FROM recommend_events WHERE post_id=%s AND version=%s
            ORDER BY created_at DESC LIMIT 1""",(post_id,row["content_version"]),
        ).fetchone()
    return {"event_id":str(event["id"]),"version":row["content_version"]}
