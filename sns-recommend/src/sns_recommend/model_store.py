from __future__ import annotations

import logging
from pathlib import Path

from .embeddings import embedding_model
from .model import Ranker, load
from .registry import active

logger = logging.getLogger(__name__)
_cache: dict[int, Ranker] = {}


def serving_model() -> tuple[Ranker | None, int | None]:
    row = active()
    if row is None or row["embedding_model"] != embedding_model():
        return None, None
    if row["id"] not in _cache:
        try:
            _cache[row["id"]] = load(Path(row["path"]))[0]
        except (OSError, RuntimeError, KeyError) as exc:
            logger.warning("Model %s unavailable: %s", row["id"], type(exc).__name__)
            return None, None
    return _cache[row["id"]], row["id"]
