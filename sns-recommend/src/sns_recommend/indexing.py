from . import source
from .config import settings
from .db import connection, source_connection
from .embeddings import embed_texts, embedding_model, vector_sql
from .sync_cursor import load_position, next_position, save_position, settled_before

BATCH_SIZE = 20


def posts_needing_index(rows):
    with connection() as conn:
        stored = {
            r["post_id"]: r
            for r in conn.execute(
                "SELECT post_id,content_version,model FROM post_embeddings WHERE post_id=ANY(%s)",
                ([post["id"] for post in rows],),
            ).fetchall()
        }
    model = embedding_model()
    needed = []
    for post in rows:
        row = stored.get(post["id"])
        current = bool(row) and (row["content_version"], row["model"]) == (post["version"], model)
        if (post["visible"] and not current) or (not post["visible"] and row):
            needed.append(post["id"])
    return needed


def index_changes():
    name = f"post_index:{embedding_model()}"
    with connection() as conn:
        position = load_position(conn, name)
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
            return result or {
                "indexed": 0,
                "mode": settings().model_mode,
                "model": embedding_model(),
            }
        reading = rows[-1]["changed_at"], rows[-1]["source_id"]


def index_posts(post_ids):
    visible = [p for p in source.posts_to_index(post_ids) if p["visible"]]
    vectors = embed_texts([p["body"] for p in visible]) if visible else []
    with connection() as conn:
        for post, vector in zip(visible, vectors, strict=True):
            conn.execute(
                """INSERT INTO post_embeddings(post_id,content_version,model,embedding)
                VALUES (%s,%s,%s,%s::vector) ON CONFLICT(post_id) DO UPDATE SET
                content_version=EXCLUDED.content_version,model=EXCLUDED.model,
                embedding=EXCLUDED.embedding""",
                (post["id"], post["version"], embedding_model(), vector_sql(vector)),
            )
        gone = list(set(post_ids) - {p["id"] for p in visible})
        conn.execute("DELETE FROM post_embeddings WHERE post_id=ANY(%s)", (gone,))
    return {"indexed": len(visible), "mode": settings().model_mode, "model": embedding_model()}
