import json
from datetime import datetime, timezone

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from . import source
from .db import connection, source_connection
from .embeddings import normalize, space, vector_sql
from .event_queue import allocate_generation
from .events import excluded_ids
from .feed import publish


def update_profile(user_id: int) -> dict[str, int]:
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    with source_connection() as conn:
        rows = conn.execute(
            """SELECT post_id FROM recommend_events WHERE user_id=%s
            AND action IN ('like','click') AND created_at<=now()
            AND created_at>now()-interval '7 days' GROUP BY post_id
            ORDER BY max(created_at) DESC,post_id DESC LIMIT 20""",
            (user_id,),
        ).fetchall()
    ids = [r["post_id"] for r in rows]
    with connection() as conn:
        rows = conn.execute(
            """SELECT post_id,content_version,embedding::text FROM post_embeddings
            WHERE post_id=ANY(%s) AND space=%s""",
            (ids, space()),
        ).fetchall()
    versions = source.current_versions(ids)
    by_id = {r["post_id"]: r for r in rows if versions.get(r["post_id"]) == r["content_version"]}
    vectors = [json.loads(by_id[i]["embedding"]) for i in ids if i in by_id][:5]
    vector = (
        normalize([sum(v[i] for v in vectors) / len(vectors) for i in range(len(vectors[0]))])
        if vectors
        else None
    )
    with connection() as conn:
        conn.execute(
            """INSERT INTO profiles(user_id,embedding,embedding_space) VALUES (%s,%s::vector,%s)
            ON CONFLICT(user_id) DO UPDATE SET embedding=EXCLUDED.embedding,embedding_space=EXCLUDED.embedding_space""",
            (
                user_id,
                vector_sql(vector) if vector is not None else None,
                space() if vector is not None else None,
            ),
        )
    return {"user_id": user_id}


def retrieve_candidates(user_id, k=30, as_of=None):
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    reference = as_of or datetime.now(timezone.utc)
    posts = source.recent_posts(user_id, reference)
    with connection() as conn:
        profile = conn.execute(
            """SELECT embedding::text,embedding_space
            FROM profiles WHERE user_id=%s""",
            (user_id,),
        ).fetchone()
        valid = bool(
            profile and profile["embedding"] is not None and profile["embedding_space"] == space()
        )
        excluded = excluded_ids(user_id)
        similar = (
            conn.execute(
                """SELECT post_id,content_version,
            1-(embedding <=> %s::vector) AS similarity FROM post_embeddings
            WHERE space=%s AND post_id=ANY(%s)""",
                (profile["embedding"], space(), [p["id"] for p in posts]),
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

    def _get_relevant_documents(self, query, *, run_manager):
        return [
            Document(page_content=p["body"], metadata={k: v for k, v in p.items() if k != "body"})
            for p in retrieve_candidates(self.user_id, self.k)
        ]


def generate_embedding(user_id):
    update_profile(user_id)
    docs = PostRetriever(user_id=user_id).invoke("recent reactions")
    with connection() as conn:
        generation = allocate_generation(conn, user_id)
    ids = [d.metadata["id"] for d in docs]
    publish(user_id, ids, "embedding", generation)
    return {"strategy": "embedding", "post_ids": ids}
