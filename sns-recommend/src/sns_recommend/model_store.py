from __future__ import annotations

from pathlib import Path

from .embeddings import embedding_model
from .model import Ranker, load
from .registry import active, version_row


def serving_model(version: int | None = None) -> tuple[Ranker | None, int | None]:
    row = version_row(version) if version else active()
    if row is None or row["embedding_model"] != embedding_model():
        return None, None
    try:
        return load(Path(row["path"]))[0], row["id"]
    except (OSError, RuntimeError, KeyError):
        return None, None
