"""The model the worker serves: the file that training wrote last."""

from __future__ import annotations

from pathlib import Path

from .config import settings
from .embeddings import embedding_model
from .model import Ranker, load

_cache: dict = {}


def active_model() -> tuple[Ranker | None, str | None]:
    path = Path(settings().model_dir) / "latest.pt"
    if not path.is_file():
        return None, None
    key = path.stat().st_mtime_ns
    if _cache.get("key") != key:
        try:
            model, info = load(path)
        except (OSError, RuntimeError, KeyError):
            return None, None
        # A model trained on other vectors cannot read today's vectors.
        usable = info.get("embedding_model") == embedding_model()
        _cache.update(key=key, model=model if usable else None, version=info["trained_until"])
    if _cache["model"] is None:
        return None, None
    return _cache["model"], _cache["version"]
