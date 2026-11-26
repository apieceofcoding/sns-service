from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from mlflow import MlflowClient
from mlflow.artifacts import download_artifacts
from mlflow.exceptions import MlflowException

from .config import settings

os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "10")

CHAMPION = "champion"


def client() -> MlflowClient:
    return MlflowClient(settings().mlflow_tracking_uri)


def experiment_id(c: MlflowClient) -> str:
    found = c.get_experiment_by_name(settings().mlflow_model)
    return found.experiment_id if found else c.create_experiment(settings().mlflow_model)


def log_run(path: str, report: dict, outcome: str) -> str:
    c = client()
    tags = {k: report[k] for k in ("data_until", "trained_until", "embedding_model")}
    run_id = c.create_run(experiment_id(c), tags={**tags, "outcome": outcome}).info.run_id
    for name, value in report["ndcg@10"].items():
        if value is not None:
            c.log_metric(run_id, f"ndcg_{name}", value)
    c.log_artifact(run_id, path, "model")
    c.set_terminated(run_id)
    return run_id


def last_run() -> dict | None:
    c = client()
    found = c.get_experiment_by_name(settings().mlflow_model)
    if found is None:
        return None
    runs = c.search_runs(
        [found.experiment_id], order_by=["attributes.start_time DESC"], max_results=1
    )
    return runs[0].data.tags if runs else None


def register(run_id: str, report: dict) -> int:
    c, name = client(), settings().mlflow_model
    if not c.search_registered_models(f"name='{name}'"):
        c.create_registered_model(name)
    source = f"{c.get_run(run_id).info.artifact_uri}/model"
    tags = {"status": "candidate", "report": json.dumps(report)}
    version = int(c.create_model_version(name, source, run_id, tags=tags).version)
    for old in versions(1000):
        if old["status"] == "candidate" and old["id"] != version:
            reject(old["id"])
    return version


def row(version) -> dict:
    report = json.loads(version.tags["report"])
    return {
        "id": int(version.version),
        "status": version.tags["status"],
        "run_id": version.run_id,
        "source": version.source,
        "embedding_model": report["embedding_model"],
        "trained_until": report["trained_until"],
        "metrics": report,
        "activated_at": version.tags.get("activated_at"),
    }


def active() -> dict | None:
    try:
        return row(client().get_model_version_by_alias(settings().mlflow_model, CHAMPION))
    except MlflowException:
        return None


def version_row(version: int) -> dict | None:
    try:
        return row(client().get_model_version(settings().mlflow_model, str(version)))
    except MlflowException:
        return None


def newest_candidate() -> dict | None:
    return next((v for v in versions(1000) if v["status"] == "candidate"), None)


def reject(version: int) -> None:
    found = version_row(version)
    if found and found["status"] == "candidate":
        client().set_model_version_tag(settings().mlflow_model, str(version), "status", "rejected")


def model_file(version: dict) -> Path:
    folder = Path(settings().model_dir) / "mlflow" / version["run_id"]
    if not folder.exists():
        download_artifacts(
            artifact_uri=version["source"],
            dst_path=str(folder),
            tracking_uri=settings().mlflow_tracking_uri,
        )
    return next(folder.rglob("*.pt"))


def promote(version: int) -> dict:
    c, name = client(), settings().mlflow_model
    if c.get_model_version(name, str(version)).tags["status"] == "rejected":
        raise ValueError("a rejected version cannot serve")
    current = active()
    if current and current["status"] == "active" and current["id"] != version:
        c.set_model_version_tag(name, str(current["id"]), "status", "retired")
    c.set_registered_model_alias(name, CHAMPION, str(version))
    c.set_model_version_tag(name, str(version), "status", "active")
    c.set_model_version_tag(name, str(version), "activated_at", datetime.now(UTC).isoformat())
    return {"active": version}


def rollback() -> dict:
    retired = [v for v in versions(1000) if v["status"] == "retired" and v["activated_at"]]
    if not retired:
        raise LookupError("no earlier version to roll back to")
    current = active()
    if current:
        client().set_model_version_tag(
            settings().mlflow_model, str(current["id"]), "status", "rejected"
        )
    return promote(max(retired, key=lambda v: v["activated_at"])["id"])


def versions(limit: int = 10) -> list[dict]:
    name = settings().mlflow_model
    found = client().search_model_versions(f"name='{name}'")
    rows = sorted((row(v) for v in found), key=lambda v: -v["id"])[:limit]
    keys = ("id", "status", "trained_until", "activated_at")
    return [{**{k: v[k] for k in keys}, "ndcg": v["metrics"]["ndcg@10"]} for v in rows]
