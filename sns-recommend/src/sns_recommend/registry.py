from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from .config import settings
from .model import Ranker, load

logging.getLogger("mlflow").setLevel(logging.ERROR)
MODEL = "ranker"
CHAMPION = "champion"
PREVIOUS = "previous"
CHALLENGER = "challenger"


def client() -> MlflowClient:
    mlflow.set_tracking_uri(settings().mlflow_tracking_uri)
    return MlflowClient()


def log_run(path: Path, report: dict, accepted: bool) -> tuple[str, int | None]:
    client()
    mlflow.set_experiment(MODEL)
    with mlflow.start_run() as run:
        tags = {k: report[k] for k in ("data_until", "trained_until", "embedding_model")}
        mlflow.set_tags({**tags, "outcome": "accepted" if accepted else "rejected"})
        scores = report["ndcg@10"].items()
        mlflow.log_metrics({f"ndcg_{k}": v for k, v in scores if v is not None})
        logged = mlflow.pytorch.log_model(
            load(path)[0],
            name="model",
            serialization_format="pickle",
            pip_requirements=["torch"],
            registered_model_name=MODEL if accepted else None,
        )
    version = logged.registered_model_version
    return run.info.run_id, int(version) if version else None


def last_run() -> dict | None:
    client()
    found = mlflow.search_runs(
        experiment_names=[MODEL],
        order_by=["attributes.start_time DESC"],
        max_results=1,
        output_format="list",
    )
    return found[0].data.tags if found else None


def row(version) -> dict:
    run = client().get_run(version.run_id).data
    scores = {k.removeprefix("ndcg_"): v for k, v in run.metrics.items()}
    return {
        "id": int(version.version),
        "embedding_model": run.tags["embedding_model"],
        "trained_until": run.tags["trained_until"],
        "ndcg": scores,
    }


def by_alias(alias: str) -> dict | None:
    try:
        return row(client().get_model_version_by_alias(MODEL, alias))
    except MlflowException:
        return None


def active() -> dict | None:
    return by_alias(CHAMPION)


def newest_candidate() -> dict | None:
    return by_alias(CHALLENGER)


def version_row(version: int) -> dict | None:
    try:
        return row(client().get_model_version(MODEL, str(version)))
    except MlflowException:
        return None


def challenge(version: int) -> None:
    client().set_registered_model_alias(MODEL, CHALLENGER, str(version))


def reject(version: int) -> None:
    candidate = newest_candidate()
    if candidate and candidate["id"] == version:
        client().delete_registered_model_alias(MODEL, CHALLENGER)


@lru_cache(maxsize=8)
def load_version(name: str, version: int) -> Ranker:
    client()
    return mlflow.pytorch.load_model(f"models:/{name}/{version}")


def model(version: dict) -> Ranker:
    return load_version(MODEL, version["id"])


def promote(version: int) -> dict:
    c, current = client(), active()
    if current and current["id"] != version:
        c.set_registered_model_alias(MODEL, PREVIOUS, str(current["id"]))
    c.set_registered_model_alias(MODEL, CHAMPION, str(version))
    reject(version)
    return {"active": version}


def rollback() -> dict:
    previous = by_alias(PREVIOUS)
    if previous is None:
        raise LookupError("no earlier version to roll back to")
    c = client()
    c.set_registered_model_alias(MODEL, CHAMPION, str(previous["id"]))
    c.delete_registered_model_alias(MODEL, PREVIOUS)
    return {"active": previous["id"]}


def versions(limit: int = 10) -> list[dict]:
    c = client()
    try:
        aliases = c.get_registered_model(MODEL).aliases
    except MlflowException:
        return []
    found = sorted(c.search_model_versions(f"name='{MODEL}'"), key=lambda v: -int(v.version))
    rows = [row(v) for v in found[:limit]]
    for item in rows:
        item["aliases"] = [a for a, v in aliases.items() if int(v) == item["id"]]
        del item["embedding_model"]
    return rows
