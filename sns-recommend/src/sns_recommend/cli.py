from __future__ import annotations

import argparse
import json

from sns_recommend.data.indexing import index_posts
from sns_recommend.data.profiles import build_user_vector
from sns_recommend.data.seed import seed
from sns_recommend.data.source_demo import change_post, seed_actions
from sns_recommend.evaluation.benchmark import benchmark
from sns_recommend.evaluation.offline import evaluate
from sns_recommend.pipelines.graph import start_graph
from sns_recommend.recommenders.baseline import baseline
from sns_recommend.recommenders.retrieval import generate_embedding
from sns_recommend.storage.postgres import initialize, source_connection
from sns_recommend.worker.scheduler import schedule_active


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "init",
            "seed",
            "status",
            "baseline",
            "source-post",
            "seed-actions",
            "index",
            "profile",
            "embedding",
            "graph",
            "evaluate",
            "benchmark",
            "schedule",
        ],
    )
    parser.add_argument("--user", type=int, default=1)
    parser.add_argument("--strategy", choices=["latest", "popular"], default="latest")
    parser.add_argument("--post", type=int, default=1001)
    parser.add_argument("--body", default="Python PostgreSQL 백엔드 실습")
    parser.add_argument("--pause-after-rerank", action="store_true")
    args = parser.parse_args()
    result: object
    if args.command == "init":
        initialize()
        result = {"schema": "ready"}
    elif args.command == "seed":
        initialize()
        result = seed()
    elif args.command == "baseline":
        result = baseline(args.user, args.strategy)
    elif args.command == "seed-actions":
        result = seed_actions()
    elif args.command == "source-post":
        result = change_post(args.post, args.body)
    elif args.command == "profile":
        vector = build_user_vector(args.user)
        result = {
            "user_id": args.user,
            "ready": vector is not None,
            "dimensions": len(vector) if vector is not None else 0,
        }
    elif args.command == "index":
        result = index_posts()
    elif args.command == "embedding":
        result = generate_embedding(args.user)
    elif args.command == "graph":
        result = start_graph(args.user, args.pause_after_rerank)
    elif args.command == "evaluate":
        result = evaluate()
    elif args.command == "benchmark":
        result = benchmark(args.user)
    elif args.command == "schedule":
        result = schedule_active()
    else:
        with source_connection() as conn:
            posts = conn.execute("SELECT count(*) AS n FROM posts").fetchone()
            users = conn.execute("SELECT count(*) AS n FROM users").fetchone()
            assert posts is not None and users is not None  # COUNT always returns a row.
            result = {"posts": posts["n"], "users": users["n"]}
    print(json.dumps(result, ensure_ascii=False, default=str))
