from __future__ import annotations

import json

from sns_recommend.storage import source
from sns_recommend.storage.postgres import connection, source_connection
from sns_recommend.providers.embeddings import normalize, space, vector_sql


def update_profile(user_id: int) -> dict[str, int | bool]:
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
    return {"user_id": user_id, "reaction_posts": len(vectors), "ready": vector is not None}

