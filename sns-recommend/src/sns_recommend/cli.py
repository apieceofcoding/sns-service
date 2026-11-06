import argparse
import json

from .baseline import baseline
from .db import initialize, source_connection
from .seed import seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "seed", "status", "baseline"])
    parser.add_argument("--user", type=int, default=1)
    parser.add_argument("--strategy", choices=["latest", "popular"], default="latest")
    args = parser.parse_args()
    if args.command == "init":
        initialize()
        result = {"schema": "ready"}
    elif args.command == "seed":
        initialize()
        result = seed()
    elif args.command == "baseline":
        result = baseline(args.user, args.strategy)
    else:
        with source_connection() as conn:
            result = {
                "posts": conn.execute("SELECT count(*) AS n FROM posts").fetchone()["n"],
                "users": conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"],
            }
    print(json.dumps(result, ensure_ascii=False, default=str))
