from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import settings
from .dataset import encode
from .embeddings import embedding_model
from .model import load
from .registry import active, last_run, log_run, model_file, promote, register
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
    sessions = prepare()[0]
    last = last_run()
    if last and not force:
        seen = datetime.fromisoformat(last["data_until"])
        new = sum(s["start"] > seen for s in sessions)
        if new < settings().retrain_min_sessions:
            return {"trained": False, "new_sessions": new}
    serving = active()
    baselines = {}
    if serving and serving["embedding_model"] == embedding_model():
        baselines["active"] = load(model_file(serving))[0]
    path = Path(settings().model_dir) / f"ranker-{datetime.now(UTC):%Y%m%d%H%M%S}.pt"
    report = train(epochs, path, baselines)
    report["data_until"] = sessions[-1]["start"].isoformat()
    accepted, reason = gate(report["ndcg@10"])
    run_id = log_run(str(path), report, "accepted" if accepted else "rejected")
    result = {"trained": True, "run": run_id, "promoted": accepted, "reason": reason, **report}
    if accepted:
        result["version"] = register(run_id, report)
        promote(result["version"])
    return result


def monitor(hours: float = 1) -> dict:
    serving = active()
    if serving is None:
        raise LookupError("no active model")
    sessions, features = prepare()
    since = datetime.now(UTC) - timedelta(hours=hours)
    recent = [s for s in sessions if s["start"] >= since]
    if not recent:
        return {"version": serving["id"], "recent_sessions": 0}
    model = load(model_file(serving))[0]
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
            logger.info(json.dumps(retrain(), default=str))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Training failed: %s", exc)
        time.sleep(600)
