from datetime import UTC, datetime

from . import source
from .db import connection
from .embeddings import embedding_model, vector_sql
from .events import excluded_ids


def retrieve_candidates(user_id, k=30, as_of=None, *, user_vector=None):
    """Candidate retrieval: semantic search plus latest and popular posts, at most k."""
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    reference = as_of or datetime.now(UTC)
    posts = source.recent_posts(user_id, reference)
    excluded = excluded_ids(user_id)
    similar = []
    if user_vector is not None:
        with connection() as conn:
            similar = conn.execute(
                """SELECT post_id,content_version,
                1-(embedding <=> %s::vector) AS similarity FROM post_embeddings
                WHERE model=%s AND post_id=ANY(%s)""",
                (vector_sql(user_vector), embedding_model(), [p["id"] for p in posts]),
            ).fetchall()
    # A vector made from an older body is ignored until the post is indexed again.
    similarity = {(r["post_id"], r["content_version"]): r["similarity"] for r in similar}
    rows = [
        {**p, "similarity": similarity.get((p["id"], p["version"]))}
        for p in posts
        if p["id"] not in excluded
    ]
    return merge_candidates(rows, k)


def merge_candidates(rows, k=30):
    semantic = sorted(
        [r for r in rows if r["similarity"] is not None],
        key=lambda r: (r["similarity"], r["id"]),
        reverse=True,
    )
    latest = sorted(rows, key=lambda r: (r["created_at"], r["id"]), reverse=True)[:10]
    popular = sorted(rows, key=lambda r: (r["likes"], r["id"]), reverse=True)[:10]
    # Keep a few fresh and popular posts even when semantic search alone could fill k.
    supplement = min(5, k // 3)
    selected = {}
    for label, group in [
        ("embedding", semantic[: k - 2 * supplement]),
        ("latest", latest[:supplement]),
        ("popular", popular[:supplement]),
        ("embedding", semantic),
        ("latest", latest),
        ("popular", popular),
    ]:
        for row in group:
            if row["id"] in selected:
                selected[row["id"]]["sources"].add(label)
            elif len(selected) < k:
                selected[row["id"]] = {**row, "sources": {label}}
    return sorted(
        ({**r, "sources": sorted(r["sources"])} for r in selected.values()),
        key=lambda r: (r["similarity"] or 0, r["created_at"], r["id"]),
        reverse=True,
    )
