from datetime import UTC, datetime, timedelta

from . import source
from .db import connection
from .embeddings import embedding_model, vector_sql
from .events import excluded_ids
from .profiles import build_user_vector


def retrieve_candidates(user_id, k=30, as_of=None, *, user_vector=None):
    if not source.user_exists(user_id):
        raise LookupError("unknown user")
    return merge_candidates(candidate_pool(user_id, as_of or datetime.now(UTC), user_vector), k)


def candidate_pool(user_id, reference, user_vector, seen_before=None):
    posts = source.recent_posts(user_id, reference)
    excluded = excluded_ids(user_id, seen_before)
    similar = []
    if user_vector is not None:
        with connection() as conn:
            similar = conn.execute(
                """SELECT post_id,content_version,
                1-(embedding <=> %s::vector) AS similarity FROM post_embeddings
                WHERE model=%s AND post_id=ANY(%s)""",
                (vector_sql(user_vector), embedding_model(), [p["id"] for p in posts]),
            ).fetchall()
    similarity = {(r["post_id"], r["content_version"]): r["similarity"] for r in similar}
    return [
        {**p, "similarity": similarity.get((p["id"], p["version"]))}
        for p in posts
        if p["id"] not in excluded
    ]


def candidate_recall(hours: float = 1, k: int = 30) -> dict:
    as_of = datetime.now(UTC) - timedelta(hours=hours)
    with connection() as conn:
        reacted = conn.execute(
            """SELECT user_id,array_agg(DISTINCT post_id) AS posts FROM user_events
            WHERE action IN ('click','like') AND deleted_at IS NULL AND occurred_at>=%s
            GROUP BY user_id""",
            (as_of,),
        ).fetchall()
    hits = dict.fromkeys(("candidates", "embedding", "latest", "popular", "random"), 0.0)
    targets = 0
    for row in reacted:
        vector = build_user_vector(row["user_id"], before=as_of)
        rows = candidate_pool(row["user_id"], as_of, vector, seen_before=as_of)
        wanted = {r["id"] for r in rows} & set(row["posts"])
        if not wanted:
            continue
        semantic = [r for r in rows if r["similarity"] is not None]
        chosen = {
            "candidates": merge_candidates(rows, k),
            "embedding": sorted(semantic, key=lambda r: r["similarity"], reverse=True)[:k],
            "latest": sorted(rows, key=lambda r: r["created_at"], reverse=True)[:k],
            "popular": sorted(rows, key=lambda r: r["likes"], reverse=True)[:k],
        }
        for name, group in chosen.items():
            hits[name] += len(wanted & {r["id"] for r in group})
        hits["random"] += len(wanted) * min(k, len(rows)) / len(rows)
        targets += len(wanted)
    return {
        "as_of": as_of,
        "users": len(reacted),
        "targets": targets,
        f"recall@{k}": {
            name: round(h / targets, 3) if targets else None for name, h in hits.items()
        },
    }


def merge_candidates(rows, k=30):
    semantic = sorted(
        [r for r in rows if r["similarity"] is not None],
        key=lambda r: (r["similarity"], r["id"]),
        reverse=True,
    )
    latest = sorted(rows, key=lambda r: (r["created_at"], r["id"]), reverse=True)[:10]
    popular = sorted(rows, key=lambda r: (r["likes"], r["id"]), reverse=True)[:10]
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
