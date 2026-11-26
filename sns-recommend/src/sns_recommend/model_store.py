from __future__ import annotations

from mlflow.exceptions import MlflowException

from .embeddings import embedding_model
from .model import Ranker, load
from .registry import active, model_file


def serving_model() -> tuple[Ranker | None, int | None]:
    row = active()
    if row is None or row["embedding_model"] != embedding_model():
        return None, None
    try:
        return load(model_file(row))[0], row["id"]
    except (OSError, RuntimeError, KeyError, StopIteration, MlflowException):
        return None, None
