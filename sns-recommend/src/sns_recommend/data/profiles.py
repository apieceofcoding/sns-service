from __future__ import annotations

import json

from sns_recommend.storage import source
from sns_recommend.storage.postgres import connection, source_connection
from sns_recommend.providers.embeddings import normalize, space


def build_user_vector(user_id: int) -> list[float] | None:
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
    return vector
