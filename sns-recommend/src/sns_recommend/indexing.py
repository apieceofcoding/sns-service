from langchain_core.documents import Document
from . import source
from .db import connection, source_connection
from .embeddings import CachedEmbeddings, space, vector_sql
from .config import settings


def index_posts(post_ids=None):
    posts = source.posts_to_index(post_ids)
    ids = [p["id"] for p in posts]
    with connection() as conn:
        rows = conn.execute("""SELECT post_id,content_version FROM post_embeddings
            WHERE space=%s AND post_id=ANY(%s)""", (space(), ids)).fetchall()
    indexed = {r["post_id"]: r["content_version"] for r in rows}
    active = [p for p in posts if p["visible"] and indexed.get(p["id"]) != p["version"]]
    if settings().model_mode in {"live","record"}:
        active = active[:20]  # Call again for the next small batch.
    documents = [Document(page_content=p["body"], metadata={"id":p["id"],"version":p["version"]})
                 for p in active]
    vectors = CachedEmbeddings().embed_documents([d.page_content for d in documents]) if documents else []
    # A post edited or deleted during the model call keeps no vector. Its own event indexes it.
    with source_connection() as original:
        locked = original.execute(
            "SELECT id,content_version,deleted_at FROM posts WHERE id=ANY(%s) FOR SHARE",
            (ids,),
        ).fetchall()
        current = {r["id"]:r["content_version"] for r in locked if r["deleted_at"] is None}
        stored = 0
        with connection() as conn:
            for post, vector in zip(active, vectors, strict=True):
                if current.get(post["id"]) != post["version"]:
                    continue
                conn.execute("""INSERT INTO post_embeddings(post_id,content_version,space,embedding)
                    VALUES (%s,%s,%s,%s::vector) ON CONFLICT(post_id) DO UPDATE SET
                    content_version=EXCLUDED.content_version,space=EXCLUDED.space,
                    embedding=EXCLUDED.embedding
                    WHERE post_embeddings.content_version<=EXCLUDED.content_version""",
                             (post["id"], post["version"], space(), vector_sql(vector)))
                stored += 1
            visible = {p["id"] for p in posts if p["visible"]}
            gone = [i for i in {*ids, *(post_ids or [])} if i not in visible]
            conn.execute("DELETE FROM post_embeddings WHERE post_id=ANY(%s)", (gone,))
    return {"indexed":stored, "mode":settings().model_mode, "space":space()}
