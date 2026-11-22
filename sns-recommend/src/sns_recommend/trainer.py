from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import experiment
from .config import settings
from .dataset import encode
from .embeddings import embedding_model
from .model import load
from .registry import active, newest_candidate, promote, register
from .training import compare, prepare, train

logger = logging.getLogger(__name__)


def gate(ndcg: dict) -> tuple[bool, str]:
    new = ndcg.get("model")
    if new is None:
        return False, "no validation sessions with reactions"
    if new < (ndcg["embedding"] or 0) + settings().promote_margin:
        return False, "not better than the embedding ranking"
    if ndcg.get("active") is not None and new < ndcg["active"]:
        return False, "worse than the serving model on the same sessions"
    return True, "better than the baselines"


def retrain(force: bool = False, epochs: int = 40) -> dict:
    if experiment.running():
        return {"trained": False, "reason": "an experiment is running; stop it first"}
    serving = active()
    if serving and not force:
        new = sum(s["start"] > serving["trained_until"] for s in prepare()[0])
        if new < settings().retrain_min_sessions:
            return {"trained": False, "new_sessions": new}
    baselines = {}
    if serving and serving["embedding_model"] == embedding_model():
        baselines["active"] = load(Path(serving["path"]))[0]
    path = Path(settings().model_dir) / f"ranker-{datetime.now(UTC):%Y%m%d%H%M%S}.pt"
    report = train(epochs, path, baselines)
    accepted, reason = gate(report["ndcg@10"])
    version = register(str(path), report, "candidate" if accepted else "rejected")
    promoted = accepted and serving is None
    if promoted:
        promote(version)
    elif accepted:
        reason = "passed the offline check; an experiment decides"
    return {"trained": True, "version": version, "promoted": promoted, "reason": reason, **report}


def step() -> dict:
    current = experiment.running()
    if current:
        ready = experiment.report(current["name"])["ready"]
        return experiment.stop() if ready else {"experiment": current["name"], "ready": False}
    result = retrain()
    candidate = newest_candidate()
    if candidate:
        started = experiment.start(f"model-{candidate['id']}-{datetime.now(UTC):%m%d%H%M}")
        result["experiment"] = started["name"]
    return result


def monitor(hours: float = 1) -> dict:
    serving = active()
    if serving is None:
        raise LookupError("no active model")
    sessions, features = prepare()
    since = datetime.now(UTC) - timedelta(hours=hours)
    recent = [s for s in sessions if s["start"] >= since and not s["ranked"]]
    if not recent:
        return {"version": serving["id"], "recent_sessions": 0}
    model = load(Path(serving["path"]))[0]
    return {
        "version": serving["id"],
        "at_training": serving["metrics"]["ndcg@10"],
        "recent_sessions": len(recent),
        "recent": compare(encode(recent, features), {"active": model}),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    while True:
        try:
            logger.info(json.dumps(step(), default=str))
        except Exception as exc:
            logger.warning("Training failed: %s", exc)
        time.sleep(600)
