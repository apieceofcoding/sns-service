"""A small transformer that reads recent reactions and predicts reactions to each candidate."""

from __future__ import annotations

from pathlib import Path

import torch
from torch import nn

from .dataset import ACTIONS, CANDIDATES, HISTORY, LABELS

# Final score is a weighted sum of predicted reactions, as in large feed rankers.
WEIGHTS = {"click": 1.0, "like": 1.0}


class Ranker(nn.Module):
    def __init__(self, dims: int = 768, width: int = 64, layers: int = 2, heads: int = 4):
        super().__init__()
        self.config = {"dims": dims, "width": width, "layers": layers, "heads": heads}
        self.post = nn.Linear(dims, width)  # post vector from the embedding model
        self.action = nn.Embedding(len(ACTIONS) + 1, width)  # click, like, reply, repost
        self.age = nn.Linear(1, width)  # hours since the reaction or since posting
        self.position = nn.Embedding(HISTORY, width)  # attention alone ignores order
        self.role = nn.Embedding(2, width)  # 0: history, 1: candidate
        self.user = nn.Parameter(torch.zeros(1, 1, width))  # always present, never padded
        layer = nn.TransformerEncoderLayer(
            width, heads, 4 * width, dropout=0.1, batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.head = nn.Linear(width, len(LABELS))
        # Candidates see the history and themselves, never each other, and the history never
        # sees candidates. A candidate's score does not depend on the other candidates.
        context = 1 + HISTORY
        size = context + CANDIDATES
        mask = torch.zeros(size, size, dtype=torch.bool)
        mask[:, context:] = True
        mask[range(context, size), range(context, size)] = False
        self.register_buffer("mask", mask, persistent=False)

    def forward(self, batch: dict[str, torch.Tensor]) -> torch.Tensor:
        """Logits with shape [sessions, candidates, reactions]."""
        table = batch["table"]
        history = (
            self.post(table[batch["history"]])
            + self.action(batch["actions"])
            + self.age(batch["history_age"][..., None])
            + self.position.weight
            + self.role.weight[0]
        )
        candidates = (
            self.post(table[batch["candidates"]])
            + self.age(batch["candidate_age"][..., None])
            + self.role.weight[1]
        )
        user = self.user.expand(len(history), -1, -1)
        start = torch.zeros(len(history), 1, dtype=torch.bool)
        padding = torch.cat([start, batch["actions"] == 0, batch["candidates"] == 0], 1)
        out = self.encoder(torch.cat([user, history, candidates], 1), self.mask, padding)
        return self.head(out[:, 1 + HISTORY :])


def score(model: Ranker, batch: dict[str, torch.Tensor]) -> torch.Tensor:
    model.eval()
    with torch.no_grad():
        probability = torch.sigmoid(model(batch))
    weights = torch.tensor([WEIGHTS[label] for label in LABELS])
    return (probability * weights).sum(-1)


def save(model: Ranker, path: Path, info: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": model.config, "state": model.state_dict(), "info": info}, path)


def load(path: Path) -> tuple[Ranker, dict]:
    data = torch.load(path, weights_only=True)
    model = Ranker(**data["config"])
    model.load_state_dict(data["state"])
    model.eval()
    return model, data["info"]
