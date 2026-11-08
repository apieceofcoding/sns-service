from __future__ import annotations

import json

from . import source
from .db import connection
from .embeddings import embedding_model, normalize


def build_user_vector(user_id: int) -> list[float] | None:
    """Average of up to 5 recently liked or clicked post vectors. Kept in memory only."""
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    with connection() as conn:
        rows = conn.execute(
            """SELECT post_id FROM user_events WHERE user_id=%s
            AND action IN ('like','reply','repost','click') AND removed_at IS NULL
            AND occurred_at>now()-interval '7 days' GROUP BY post_id
            ORDER BY max(occurred_at) DESC,post_id DESC LIMIT 20""",
            (user_id,),
        ).fetchall()
        ids = [r["post_id"] for r in rows]
        rows = conn.execute(
            """SELECT post_id,content_version,embedding::text FROM post_embeddings
            WHERE post_id=ANY(%s) AND model=%s""",
            (ids, embedding_model()),
        ).fetchall()
    versions = source.current_versions(ids)
    by_id = {r["post_id"]: r for r in rows if versions.get(r["post_id"]) == r["content_version"]}
    vectors = [json.loads(by_id[i]["embedding"]) for i in ids if i in by_id][:5]
    if not vectors:
        return None
    return normalize([sum(v[i] for v in vectors) / len(vectors) for i in range(len(vectors[0]))])
