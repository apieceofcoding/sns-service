from . import source
from .config import settings
from .db import connection
from .embeddings import embed_texts, embedding_model, vector_sql

BATCH_SIZE = 20


def index_changes():
    model = embedding_model()
    current = source.post_hashes()
    with connection() as conn:
        conn.execute(
            "DELETE FROM post_embeddings WHERE model<>%s OR NOT post_id=ANY(%s)",
            (model, list(current)),
        )
        rows = conn.execute("SELECT post_id,content_hash FROM post_embeddings").fetchall()
    stored = {r["post_id"]: r["content_hash"] for r in rows}
    pending = [post_id for post_id, h in current.items() if stored.get(post_id) != h][:BATCH_SIZE]
    if pending:
        bodies = source.post_bodies(pending)
        vectors = embed_texts([bodies[post_id] for post_id in pending])
        with connection() as conn:
            for post_id, vector in zip(pending, vectors, strict=True):
                conn.execute(
                    """INSERT INTO post_embeddings(post_id,content_hash,model,embedding)
                    VALUES (%s,%s,%s,%s::vector) ON CONFLICT(post_id) DO UPDATE SET
                    content_hash=EXCLUDED.content_hash,model=EXCLUDED.model,
                    embedding=EXCLUDED.embedding""",
                    (post_id, current[post_id], model, vector_sql(vector)),
                )
    return {"indexed": len(pending), "mode": settings().model_mode, "model": model}
