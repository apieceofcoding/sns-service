from __future__ import annotations

from sns_recommend.core.config import settings
from sns_recommend.core.types import GenerationResult, RankingInput
from sns_recommend.data.profiles import build_user_vector
from sns_recommend.providers.rerank import PROMPT_VERSION, ranking_strategy, rerank_candidates
from sns_recommend.recommenders.ranking import diversify, validate_ranking
from sns_recommend.recommenders.retrieval import retrieve_candidates
from sns_recommend.storage import source
from sns_recommend.storage.event_queue import allocate_generation, current_generation
from sns_recommend.storage.feeds import publish
from sns_recommend.storage.postgres import connection


def prepare_inputs(user_id: int) -> RankingInput:
    user_vector = build_user_vector(user_id)
    candidates = retrieve_candidates(user_id, user_vector=user_vector)
    with connection() as conn:
        actions = conn.execute(
            """SELECT action,post_id FROM user_events WHERE user_id=%s AND removed_at IS NULL
            AND action IN ('click','like','reply','repost')
            ORDER BY occurred_at DESC LIMIT 10""",
            (user_id,),
        ).fetchall()
    bodies = source.post_bodies([row["post_id"] for row in actions])
    history = [
        {**row, "body": bodies[row["post_id"]]} for row in actions if row["post_id"] in bodies
    ]
    return {
        "user_id": user_id,
        "history": history,
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
