from __future__ import annotations

from pathlib import Path

from .config import settings
from .embeddings import embedding_model
from .model import Ranker, load


def serving_model() -> tuple[Ranker | None, str | None]:
    path = Path(settings().model_dir) / "latest.pt"
    if not path.is_file():
        return None, None
    model, info = load(path)
    if info.get("embedding_model") != embedding_model():
        return None, None
    return model, info["trained_until"]
