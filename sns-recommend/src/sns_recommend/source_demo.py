"""Transactional Outbox demo. It plays the SNS side: one transaction changes a post
and records the event. Real SNS code does this in Spring with its own authentication."""
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from psycopg.types.json import Jsonb
from .db import source_connection
from .events import Event
from .seed import advance_identity


def change_post(post_id, body, author_id=1):
    now = datetime.now(timezone.utc)
    with source_connection() as conn:
        row = conn.execute("""INSERT INTO posts(id,content,user_id,created_at,modified_at)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET content=EXCLUDED.content,
            modified_at=EXCLUDED.modified_at,content_version=posts.content_version+1
            RETURNING content_version""", (post_id, body, author_id, now, now)).fetchone()
        advance_identity(conn, "posts")
        # The event carries only the ID and version. The body stays in the SNS database.
        event = Event(event_id=uuid4(), kind="post.updated", post_id=post_id,
                      version=row["content_version"])
        conn.execute("INSERT INTO recommend_outbox(id,event) VALUES (%s,%s)",
                     (event.event_id, Jsonb(event.model_dump(mode="json"))))
    return {"event_id": str(event.event_id), "version": row["content_version"]}


def relay(url="http://localhost:8001"):
    count = 0
    with source_connection() as conn:
        rows = conn.execute("""SELECT * FROM recommend_outbox
            WHERE delivered_at IS NULL ORDER BY created_at""").fetchall()
    for row in rows:
        response = httpx.post(url + "/internal/events", json=row["event"], timeout=5)
        response.raise_for_status()
        with source_connection() as conn:
            conn.execute("UPDATE recommend_outbox SET delivered_at=now() WHERE id=%s",
                         (row["id"],))
        count += 1
    return {"delivered": count}
