import argparse
import json

from .baseline import baseline
from .db import initialize, source_connection
from .indexing import index_changes
from .profiles import build_user_vector
from .seed import seed
from .source_demo import change_post, seed_actions


def main():
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
        ],
    )
    parser.add_argument("--user", type=int, default=1)
    parser.add_argument("--strategy", choices=["latest", "popular"], default="latest")
    parser.add_argument("--post", type=int, default=1001)
    parser.add_argument("--body", default="Python PostgreSQL 백엔드 실습")
    args = parser.parse_args()
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
        result = index_changes()
    else:
        with source_connection() as conn:
            result = {
                "posts": conn.execute("SELECT count(*) AS n FROM posts").fetchone()["n"],
                "users": conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"],
            }
    print(json.dumps(result, ensure_ascii=False, default=str))
