from __future__ import annotations

from langchain_core.documents import Document

from sns_recommend.core.config import settings
from sns_recommend.core.types import DatabaseRow, IndexResult
from sns_recommend.providers.embeddings import ModelEmbeddings, space, vector_sql
from sns_recommend.storage import source
from sns_recommend.storage.postgres import connection, source_connection
from sns_recommend.storage.sync_cursor import (
    load_position,
    next_position,
    save_position,
    settled_before,
)

BATCH_SIZE = 20


def posts_needing_index(rows: list[DatabaseRow]) -> list[int]:
    """Compare changed posts with stored vectors. Unchanged posts cost no model call."""
    with connection() as conn:
        stored = {
            r["post_id"]: r
            for r in conn.execute(
                "SELECT post_id,content_version,space FROM post_embeddings WHERE post_id=ANY(%s)",
                ([post["id"] for post in rows],),
            ).fetchall()
        }
    needed: list[int] = []
    for post in rows:
        row = stored.get(post["id"])
        if post["visible"]:
            if not row or row["content_version"] != post["version"] or row["space"] != space():
                needed.append(post["id"])
        elif row:
            needed.append(post["id"])
    return needed


def index_changes() -> IndexResult:
    """Index the next changed posts. The cursor moves only after the model call succeeds."""
    # Another embedding space starts from the beginning, which re-indexes every post.
    name = f"post_index:{space()}"
    with connection() as conn:
        position = load_position(conn, name)
    # The saved cursor stays behind the overlap window, but reading must still move through it.
    reading = position
    while True:
        with source_connection() as original:
            settled = settled_before(original)
        rows = source.changed_posts(reading, BATCH_SIZE)
        needed = posts_needing_index(rows)
        result = index_posts(needed) if needed else None
        position = next_position(rows, position, settled)
        with connection() as conn:
            save_position(conn, name, position)
        if needed or len(rows) < BATCH_SIZE:
            return result or {"indexed": 0, "mode": settings().model_mode, "space": space()}
        reading = rows[-1]["changed_at"], rows[-1]["cursor_id"]


def index_posts(post_ids: list[int]) -> IndexResult:
    posts = source.posts_to_index(post_ids)
    ids = [p["id"] for p in posts]
    with connection() as conn:
        rows = conn.execute(
            "SELECT post_id,content_version FROM post_embeddings WHERE space=%s AND post_id=ANY(%s)",
            (space(), ids),
        ).fetchall()
    indexed = {r["post_id"]: r["content_version"] for r in rows}
    active = [p for p in posts if p["visible"] and indexed.get(p["id"]) != p["version"]]
    documents = [
        Document(page_content=p["body"], metadata={"id": p["id"], "version": p["version"]})
        for p in active
    ]
    vectors = (
        ModelEmbeddings().embed_documents([d.page_content for d in documents]) if documents else []
    )
    # A post edited or deleted during the model call keeps no vector. Its own event indexes it.
    with source_connection() as original:
        locked = original.execute(
            "SELECT id,content_version,deleted_at FROM posts WHERE id=ANY(%s) FOR SHARE",
            (ids,),
        ).fetchall()
        current = {r["id"]: r["content_version"] for r in locked if r["deleted_at"] is None}
        stored = 0
        with connection() as conn:
            for post, vector in zip(active, vectors, strict=True):
                if current.get(post["id"]) != post["version"]:
                    continue
                conn.execute(
                    """INSERT INTO post_embeddings(post_id,content_version,space,embedding)
                    VALUES (%s,%s,%s,%s::vector) ON CONFLICT(post_id) DO UPDATE SET
                    content_version=EXCLUDED.content_version,space=EXCLUDED.space,
                    embedding=EXCLUDED.embedding
                    WHERE post_embeddings.content_version<=EXCLUDED.content_version""",
                    (post["id"], post["version"], space(), vector_sql(vector)),
                )
                stored += 1
            visible = {p["id"] for p in posts if p["visible"]}
            gone = list(set(post_ids) - visible)
            conn.execute("DELETE FROM post_embeddings WHERE post_id=ANY(%s)", (gone,))
    return {"indexed": stored, "mode": settings().model_mode, "space": space()}
