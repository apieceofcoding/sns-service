from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import cast

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from sns_recommend.core.types import Candidate, DatabaseRow, GenerationResult
from sns_recommend.data.events import excluded_ids
from sns_recommend.providers.embeddings import CachedEmbeddings, normalize, space, vector_sql
from sns_recommend.storage import source
from sns_recommend.storage.feeds import publish
from sns_recommend.storage.jobs import allocate_generation, current_generation, enqueue
from sns_recommend.storage.postgres import connection


def interests_hash(interests: str) -> str:
    return hashlib.sha256(interests.encode()).hexdigest()


def update_profile(user_id: int) -> dict[str, int]:
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    interests = source.interests(user_id)
    if not interests:
        return {"user_id": user_id}  # No stated interests yet: latest and popular only.
    with connection() as conn:
        reacted = conn.execute(
            """SELECT p.post_id,p.content_version,p.embedding::text FROM events e
            JOIN post_embeddings p ON p.post_id=e.post_id
            WHERE e.user_id=%s AND e.kind IN ('like','click') AND p.space=%s
            AND e.occurred_at<=now() AND e.occurred_at>now()-interval '7 days'
            GROUP BY p.post_id ORDER BY max(e.occurred_at) DESC,p.post_id DESC LIMIT 20""",
            (user_id, space()),
        ).fetchall()
    # Use a reaction only while its post is visible and the vector matches the current body.
    versions = source.current_versions([r["post_id"] for r in reacted])
    positives = [r for r in reacted if versions.get(r["post_id"]) == r["content_version"]][:5]
    # Cached initial text vector, plus stored post vectors. No model call per event.
    base = CachedEmbeddings().embed_query(interests)
    vectors = [json.loads(p["embedding"]) for p in positives]
    mixed = (
        normalize(
            [
                0.7 * x + 0.3 * sum(v[i] for v in vectors) / max(1, len(vectors))
                for i, x in enumerate(base)
            ]
        )
        if vectors
        else base
    )
    with connection() as conn:
        conn.execute(
            """INSERT INTO profiles(user_id,embedding,embedding_space,interests_hash)
            VALUES (%s,%s::vector,%s,%s) ON CONFLICT(user_id) DO UPDATE SET
            embedding=EXCLUDED.embedding,embedding_space=EXCLUDED.embedding_space,
            interests_hash=EXCLUDED.interests_hash""",
            (user_id, vector_sql(mixed), space(), interests_hash(interests)),
        )
    return {"user_id": user_id}


def retrieve_candidates(
    user_id: int, k: int = 30, as_of: datetime | None = None
) -> list[Candidate]:
    if not 1 <= k <= 50:
        raise ValueError("candidate count must be between 1 and 50")
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    reference = as_of or datetime.now(UTC)
    # Posts come from the SNS database. The recommend database adds similarity by ID.
    posts = source.recent_posts(user_id, reference)
    interests = source.interests(user_id)
    with connection() as conn:
        profile = conn.execute(
            """SELECT embedding::text,embedding_space,interests_hash
            FROM profiles WHERE user_id=%s""",
            (user_id,),
        ).fetchone()
        valid = bool(
            profile
            and interests
            and profile["embedding"] is not None
            and profile["embedding_space"] == space()
            and profile["interests_hash"] == interests_hash(interests)
        )
        excluded = excluded_ids(conn, user_id)
        similar = (
            conn.execute(
                """SELECT post_id,content_version,1-(embedding <=> %s::vector) AS similarity
                FROM post_embeddings WHERE space=%s AND post_id=ANY(%s)""",
                (profile["embedding"], space(), [p["id"] for p in posts]),
            ).fetchall()
            if valid and profile
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
    # Keep fresh and popular candidates even when semantic search already fills k.
    supplement = min(5, k // 3)
    selected: dict[int, DatabaseRow] = {}
    for group in (
        semantic[: k - 2 * supplement],
        latest[:supplement],
        popular[:supplement],
        semantic,
        latest,
        popular,
    ):
        for row in group:
            if len(selected) < k:
                selected[row["id"]] = merged[row["id"]]
    ranked = sorted(
        selected.values(),
        key=lambda r: (r["similarity"] or 0, r["created_at"], r["id"]),
        reverse=True,
    )
    return [cast(Candidate, {**r, "created_at": r["created_at"].isoformat()}) for r in ranked]


class PostRetriever(BaseRetriever):
    user_id: int
    k: int = 30

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        return [
            Document(page_content=p["body"], metadata={k: v for k, v in p.items() if k != "body"})
            for p in retrieve_candidates(self.user_id, self.k)
        ]


def generate_embedding(user_id: int) -> GenerationResult:
    with connection() as conn:
        generation = allocate_generation(conn, user_id)
    update_profile(user_id)
    docs = PostRetriever(user_id=user_id).invoke("stored user interests")
    ids = [d.metadata["id"] for d in docs]
    with connection() as conn:
        published = current_generation(conn, user_id) == generation and publish(
            user_id, ids, "embedding", generation
        )
    return {"strategy": "embedding", "post_ids": ids, "published": published}


def process_profile(user_id: int) -> None:
    update_profile(user_id)
    with connection() as conn:
        enqueue(conn, "build", user_id=user_id)
