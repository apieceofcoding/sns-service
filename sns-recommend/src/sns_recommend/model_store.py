from __future__ import annotations

from mlflow.exceptions import MlflowException

from .embeddings import embedding_model
from .model import Ranker
from .registry import active, model, version_row


def serving_model(version: int | None = None) -> tuple[Ranker | None, int | None]:
    row = version_row(version) if version else active()
    if row is None or row["embedding_model"] != embedding_model():
        return None, None
    try:
        return model(row), row["id"]
    except (OSError, RuntimeError, MlflowException):
        return None, None
