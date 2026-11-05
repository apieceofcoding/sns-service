from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from sns_recommend.core.config import settings
from sns_recommend.core.resources import resource_directory
from sns_recommend.core.types import (
    Candidate,
    EvaluationReport,
    QualityRow,
    RankingInput,
    StabilityRow,
)
from sns_recommend.evaluation.metrics import ndcg_at_k, recall_at_k
from sns_recommend.providers.embeddings import ModelEmbeddings, FixtureEmbeddings, normalize
from sns_recommend.providers.rerank import PROMPT_VERSION, ranking_strategy, rerank_candidates
from sns_recommend.recommenders.ranking import diversify, validate_ranking
from sns_recommend.recommenders.retrieval import merge_candidates


def evaluate(path: str | Path | None = None, k: int = 10) -> EvaluationReport:
    source = (
        Path(path) if path is not None else resource_directory("data").joinpath("evaluation.json")
    )
    data = json.loads(source.read_text())
    cutoff = datetime.fromisoformat(data["context_cutoff"])
    observed = datetime.fromisoformat(data["evaluation_time"])
    past = [a for a in data["actions"] if datetime.fromisoformat(a["at"]) <= cutoff]
    corpus = [
        p for p in data["posts"] if cutoff < datetime.fromisoformat(p["created_at"]) <= observed
    ]
    embedding = FixtureEmbeddings() if settings().model_mode == "fixture" else ModelEmbeddings()
    vectors = embedding.embed_documents([p["body"] for p in data["posts"]])
    index = {p["id"]: v for p, v in zip(data["posts"], vectors, strict=True)}
    rows: list[QualityRow] = []
    stability: list[StabilityRow] = []
    for user in data["users"]:
        history = [a for a in past if a["user_id"] == user["id"]]
        liked = [index[a["post_id"]] for a in history if a["action"] in ("like", "click")][-5:]
        profile = (
            normalize([sum(v[i] for v in liked) / len(liked) for i in range(len(liked[0]))])
            if liked
            else None
        )
        candidates = cast(
            list[Candidate],
            merge_candidates(
                [
                    {
                        **p,
                        "similarity": sum(
                            x * y for x, y in zip(profile, index[p["id"]], strict=True)
                        )
                        if profile is not None
                        else None,
                    }
                    for p in corpus
                ]
            ),
        )
        inputs: RankingInput = {
            "history": history,
            "candidates": candidates,
            "model": settings().rerank_model,
            "mode": settings().model_mode,
            "prompt_version": PROMPT_VERSION,
        }
        response = rerank_candidates(inputs)
        ordered = validate_ranking(candidates, response["ordered_ids"])
        orders = {
            "latest": [
                p["id"] for p in sorted(corpus, key=lambda p: p["created_at"], reverse=True)
            ],
            "popular": [p["id"] for p in sorted(corpus, key=lambda p: p["likes"], reverse=True)],
            "embedding": [p["id"] for p in candidates],
            ranking_strategy(response["mode"]): diversify(candidates, ordered),
        }
        labels = {str(p["id"]): int(p["topic"] == user["topic"]) for p in corpus}
        lookup = {p["id"]: p for p in corpus}
        for strategy, ids in orders.items():
            rows.append(
                {
                    "user_id": user["id"],
                    "strategy": strategy,
                    "recall_at_k": round(recall_at_k(ids, labels, k), 4),
                    "ndcg_at_k": round(ndcg_at_k(ids, labels, k), 4),
                    "author_count_at_k": len({lookup[i]["author_id"] for i in ids[:k]}),
                    "topic_count_at_k": len({lookup[i]["topic"] for i in ids[:k]}),
                }
            )
        second = rerank_candidates({**inputs, "candidates": list(reversed(candidates))})
        other = validate_ranking(candidates, second["ordered_ids"])
        stability.append(
            {
                "user_id": user["id"],
                "top_k_overlap": len(set(ordered[:k]) & set(other[:k])) / k,
                "same_order": ordered == other,
            }
        )
    report: EvaluationReport = {
        "dataset": "synthetic",
        "model_mode": settings().model_mode,
        "k": k,
        "context_cutoff": data["context_cutoff"],
        "evaluation_time": data["evaluation_time"],
        "rows": rows,
        "input_order_stability": stability,
        "interpretation": "Offline synthetic relevance; not real CTR or user satisfaction.",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report
