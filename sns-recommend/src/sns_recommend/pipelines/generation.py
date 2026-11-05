from __future__ import annotations

from sns_recommend.core.config import settings
from sns_recommend.core.types import RankingInput
from sns_recommend.data.profiles import build_user_vector
from sns_recommend.providers.rerank import PROMPT_VERSION
from sns_recommend.recommenders.retrieval import retrieve_candidates
from sns_recommend.storage import source
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
