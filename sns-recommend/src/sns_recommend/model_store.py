"""The model the worker serves: the active version in the registry."""

from __future__ import annotations

import logging
from pathlib import Path

from .embeddings import embedding_model
from .model import Ranker, load
from .registry import active

logger = logging.getLogger(__name__)
_cache: dict = {}


def active_model() -> tuple[Ranker | None, int | None]:
    """None means: serve the retrieval order instead."""
    row = active()
    # A model trained on other vectors cannot read today's vectors.
    if row is None or row["embedding_model"] != embedding_model():
        return None, None
    if _cache.get("version") != row["id"]:
        try:
            model, _ = load(Path(row["path"]))
        except (OSError, RuntimeError, KeyError) as exc:
            logger.warning("Model %s unavailable: %s", row["id"], type(exc).__name__)
            return None, None
        _cache.update(version=row["id"], model=model)
    return _cache["model"], row["id"]
