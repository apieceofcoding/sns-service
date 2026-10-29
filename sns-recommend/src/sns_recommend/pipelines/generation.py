from __future__ import annotations

from sns_recommend.core.config import settings
from sns_recommend.core.types import GenerationResult, RankingInput
from sns_recommend.providers.rerank import PROMPT_VERSION, ranking_strategy, rerank_candidates
from sns_recommend.recommenders.ranking import diversify, validate_ranking
from sns_recommend.recommenders.retrieval import retrieve_candidates
from sns_recommend.data.profiles import build_user_vector
from sns_recommend.storage.event_queue import allocate_generation, current_generation
from sns_recommend.storage.feeds import publish
from sns_recommend.storage.postgres import connection, source_connection


def prepare_inputs(user_id: int) -> RankingInput:
    user_vector = build_user_vector(user_id)
    candidates = retrieve_candidates(user_id, user_vector=user_vector)
    with source_connection() as conn:
        history = conn.execute(
            """SELECT e.action,e.post_id,p.content AS body FROM recommend_events e JOIN posts p ON p.id=e.post_id WHERE e.user_id=%s AND p.deleted_at IS NULL
            AND e.created_at<=now() AND e.action IN ('click','like','not_interested')
            ORDER BY e.created_at DESC LIMIT 10""",
            (user_id,),
        ).fetchall()
    return {
        "user_id": user_id,
        "history": [
            {"action": row["action"], "post_id": row["post_id"], "body": row["body"]}
            for row in history
        ],
        "candidates": candidates,
        "prompt_version": PROMPT_VERSION,
        "model": settings().rerank_model,
        "mode": settings().model_mode,
    }


def generate(user_id: int) -> GenerationResult:
    with connection() as conn:
        generation = allocate_generation(conn, user_id)
    inputs = prepare_inputs(user_id)
    candidates = inputs["candidates"]
    try:
        response = rerank_candidates(inputs)
        ordered = validate_ranking(candidates, response.get("ordered_ids"))
        strategy = ranking_strategy(response["mode"])
    except Exception:
        ordered, strategy = [p["id"] for p in candidates], "rules_fallback"
    ids = diversify(candidates, ordered)
    with connection() as conn:
        published = current_generation(conn, user_id) == generation and publish(
            user_id, ids, strategy, generation
        )
    return {"strategy": strategy, "post_ids": ids, "published": published}
