"""Continuous training: retrain on new data, check the result, and promote only if it is better."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import settings
from .dataset import encode
from .embeddings import embedding_model
from .model import load, save
from .registry import active, promote, register
from .training import compare, fit, prepare, split

logger = logging.getLogger(__name__)
TOLERANCE = 0.005


def gate(ndcg: dict) -> tuple[bool, str]:
    candidate = ndcg.get("candidate")
    if candidate is None:
        return False, "no validation sessions with reactions"
    if candidate < (ndcg["embedding"] or 0) + settings().promote_margin:
        return False, "not better than the embedding ranking"
    if ndcg.get("active") is not None and candidate < ndcg["active"] - TOLERANCE:
        return False, "worse than the serving model on the same sessions"
    return True, "better than the baselines"


def retrain(force: bool = False, epochs: int = 40) -> dict:
    serving = active()
    sessions, features = prepare()
    if serving and not force:
        new = sum(s["start"] > serving["trained_until"] for s in sessions)
        if new < settings().retrain_min_sessions:
            return {"trained": False, "new_sessions": new}
    train_sessions, valid_sessions = split(sessions)
    if len(train_sessions) < 20 or not features:
        raise ValueError("not enough sessions; run simulate and the event worker first")
    started = time.perf_counter()
    model = fit(encode(train_sessions, features), epochs)
    models = {"candidate": model}
    if serving and serving["embedding_model"] == embedding_model():
        models["active"] = load(Path(serving["path"]))[0]
    report = {
        "sessions": {"train": len(train_sessions), "valid": len(valid_sessions)},
        "trained_until": train_sessions[-1]["start"].isoformat(),
        "embedding_model": embedding_model(),
        "seconds": round(time.perf_counter() - started, 1),
        "ndcg@10": compare(encode(valid_sessions, features), models),
    }
    accepted, reason = gate(report["ndcg@10"])
    path = Path(settings().model_dir) / f"ranker-{datetime.now(UTC):%Y%m%d%H%M%S}.pt"
    save(model, path, report)
    version = register(str(path), report, "candidate" if accepted else "rejected")
    if accepted:
        promote(version)
    return {"trained": True, "version": version, "promoted": accepted, "reason": reason, **report}


def monitor(hours: float = 1) -> dict:
    """Score the serving model on the latest visits. A drop means tastes have moved."""
    serving = active()
    if serving is None:
        raise LookupError("no active model")
    sessions, features = prepare()
    since = datetime.now(UTC) - timedelta(hours=hours)
    recent = [s for s in sessions if s["start"] >= since]
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
    parser = argparse.ArgumentParser(description="Retrain the ranker when enough new data arrives")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=600, help="seconds between checks")
    args = parser.parse_args()
    while True:
        try:
            result = retrain()
            logger.info(json.dumps(result, default=str))
        except Exception as exc:
            logger.warning("Training failed: %s", exc)
        if args.once:
            return
        time.sleep(args.interval)
