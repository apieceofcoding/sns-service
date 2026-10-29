from datetime import datetime, timezone

from langchain_core.documents import Document
from .profiles import build_user_vector
from langchain_core.retrievers import BaseRetriever

from . import source
from .db import connection
from .embeddings import space, vector_sql
from .events import excluded_ids
from .feed import publish


def retrieve_candidates(user_id, k=30, as_of=None, *, user_vector=None):
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    reference = as_of or datetime.now(timezone.utc)
    posts = source.recent_posts(user_id, reference)
    with connection() as conn:
        valid = user_vector is not None
        excluded = excluded_ids(user_id)
        similar = (
            conn.execute(
                """SELECT post_id,content_version,
            1-(embedding <=> %s::vector) AS similarity FROM post_embeddings
            WHERE space=%s AND post_id=ANY(%s)""",
                (vector_sql(user_vector), space(), [p["id"] for p in posts]),
            ).fetchall()
            if valid
            else []
        )
    # A vector made from an older body is ignored until the post is indexed again.
    similarity = {(r["post_id"], r["content_version"]): r["similarity"] for r in similar}
    rows = [
        {**p, "similarity": similarity.get((p["id"], p["version"]))}
        for p in posts
        if p["id"] not in excluded
    ]
    semantic = sorted(
        [r for r in rows if valid and r["similarity"] is not None],
        key=lambda r: (r["similarity"], r["id"]),
        reverse=True,
    )[:k]
    latest = sorted(rows, key=lambda r: (r["created_at"], r["id"]), reverse=True)[:10]
    popular = sorted(rows, key=lambda r: (r["likes"], r["id"]), reverse=True)[:10]
    merged = {}
    for label, group in [("embedding", semantic), ("latest", latest), ("popular", popular)]:
        for row in group:
            if row["id"] not in merged:
                merged[row["id"]] = {**row, "sources": []}
            merged[row["id"]]["sources"].append(label)
    ranked = sorted(
        merged.values(),
        key=lambda r: (r["similarity"] or 0, r["created_at"], r["id"]),
        reverse=True,
    )[:k]
    return [{**r, "created_at": r["created_at"].isoformat()} for r in ranked]


class PostRetriever(BaseRetriever):
    user_id: int
    k: int = 30
    user_vector: list[float] | None = None

    def _get_relevant_documents(self, query, *, run_manager):
        return [
            Document(page_content=p["body"], metadata={k: v for k, v in p.items() if k != "body"})
            for p in retrieve_candidates(self.user_id, self.k, user_vector=self.user_vector)
        ]


def generate_embedding(user_id):
    user_vector = build_user_vector(user_id)
    docs = PostRetriever(user_id=user_id, user_vector=user_vector).invoke("recent reactions")
    ids = [d.metadata["id"] for d in docs]
    publish(user_id, ids, "embedding")
    return {"strategy": "embedding", "post_ids": ids}
