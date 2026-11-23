from __future__ import annotations

import json
from datetime import UTC, datetime

from . import source
from .db import connection
from .embeddings import embedding_model, normalize


def build_user_vector(user_id: int, before: datetime | None = None) -> list[float] | None:
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    reference = before or datetime.now(UTC)
    with connection() as conn:
        row = conn.execute(
            """SELECT avg(embedding)::text AS mean FROM (
            SELECT p.embedding FROM user_events e JOIN post_embeddings p USING (post_id)
            WHERE e.user_id=%s AND e.action IN ('like','reply','repost','click')
            AND e.deleted_at IS NULL AND p.model=%s
            AND e.occurred_at>%s-interval '7 days' AND e.occurred_at<%s
            GROUP BY p.post_id ORDER BY max(e.occurred_at) DESC,p.post_id DESC LIMIT 5) recent""",
            (user_id, embedding_model(), reference, reference),
        ).fetchone()
    return normalize(json.loads(row["mean"])) if row["mean"] else None
