from __future__ import annotations

import math
import time
from pathlib import Path

import torch
from torch import nn

from .config import settings
from .dataset import build_sessions, encode, load_events, post_features
from .embeddings import embedding_model
from .model import Ranker, save, score


def split(sessions: list[dict], valid_ratio: float = 0.25) -> tuple[list[dict], list[dict]]:
    cut = int(len(sessions) * (1 - valid_ratio))
    return sessions[:cut], [s for s in sessions[cut:] if not s["ranked"]]


def fit(
    batch: dict[str, torch.Tensor], epochs: int = 40, seed: int = 0, batch_size: int = 32
) -> Ranker:
    torch.manual_seed(seed)
    model = Ranker(dims=batch["table"].shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
    shown = batch["candidates"] > 0
    for _ in range(epochs):
        model.train()
        for rows in torch.randperm(len(shown)).split(batch_size):
            part = {k: v if k == "table" else v[rows] for k, v in batch.items()}
            logits = model(part)
            loss = nn.functional.binary_cross_entropy_with_logits(
                logits[shown[rows]], part["labels"][shown[rows]]
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return model


def ndcg(scores: torch.Tensor, batch: dict[str, torch.Tensor], k: int = 10) -> float | None:
    relevance = batch["labels"].sum(-1)
    values = []
    for row in range(len(scores)):
        shown = batch["candidates"][row] > 0
        rel = relevance[row][shown].tolist()
        if not any(rel):
            continue
        predicted = scores[row][shown].tolist()
        order = sorted(range(len(rel)), key=lambda i: -predicted[i])[:k]
        dcg = sum(rel[i] / math.log2(rank + 2) for rank, i in enumerate(order))
        ideal = sum(r / math.log2(i + 2) for i, r in enumerate(sorted(rel, reverse=True)[:k]))
        values.append(dcg / ideal)
    return round(sum(values) / len(values), 4) if values else None


def embedding_scores(batch: dict[str, torch.Tensor]) -> torch.Tensor:
    table = batch["table"]
    users = []
    for row in batch["history"]:
        recent = list(dict.fromkeys(i for i in reversed(row.tolist()) if i))[:5]
        vector = table[recent].mean(0) if recent else torch.zeros(table.shape[1])
        users.append(vector / (vector.norm() or 1))
    return (table[batch["candidates"]] * torch.stack(users)[:, None]).sum(-1)


def compare(batch: dict[str, torch.Tensor], models: dict[str, Ranker]) -> dict[str, float | None]:
    report = {
        "latest": ndcg(-batch["candidate_age"], batch),
        "embedding": ndcg(embedding_scores(batch), batch),
    }
    return report | {name: ndcg(score(model, batch), batch) for name, model in models.items()}


def prepare() -> tuple[list[dict], dict[int, dict]]:
    sessions = build_sessions(load_events())
    ids = {p for s in sessions for p in s["candidates"] + [h[0] for h in s["history"]]}
    return sessions, post_features(ids)


def train(epochs: int = 40, path: Path | None = None, baselines: dict | None = None) -> dict:
    sessions, features = prepare()
    train_sessions, valid_sessions = split(sessions[-settings().train_sessions :])
    if len(train_sessions) < 20 or not features:
        raise ValueError("not enough sessions; run simulate and the event worker first")
    started = time.perf_counter()
    model = fit(encode(train_sessions, features), epochs)
    report = {
        "sessions": {"train": len(train_sessions), "valid": len(valid_sessions)},
        "trained_until": train_sessions[-1]["start"].isoformat(),
        "embedding_model": embedding_model(),
        "seconds": round(time.perf_counter() - started, 1),
        "ndcg@10": compare(encode(valid_sessions, features), {"model": model, **(baselines or {})}),
    }
    save(model, path or Path(settings().model_dir) / "latest.pt", report)
    return report
