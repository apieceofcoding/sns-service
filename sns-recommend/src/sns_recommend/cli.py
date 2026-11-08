import argparse
import json

from .db import initialize, source_connection


def main():
    parser = argparse.ArgumentParser(prog="sns-recommend")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "seed", "status", "index", "models", "rollback"):
        commands.add_parser(name)
    simulate = commands.add_parser("simulate", help="synthetic readers see posts and react")
    simulate.add_argument("--users", type=int, default=300)
    simulate.add_argument("--sessions", type=int, default=15)
    simulate.add_argument("--hours", type=float, default=4)
    simulate.add_argument(
        "--shift", action="store_true", help="every simulated reader changes taste"
    )
    post = commands.add_parser("source-post", help="create or edit a post in the SNS database")
    post.add_argument("--post", type=int, default=1001)
    post.add_argument("--body", default="Python PostgreSQL 백엔드 실습")
    for name in ("profile", "candidates", "generate"):
        commands.add_parser(name).add_argument("--user", type=int, default=7)
    baseline = commands.add_parser("baseline")
    baseline.add_argument("--user", type=int, default=7)
    baseline.add_argument("--strategy", choices=["latest", "popular"], default="latest")
    commands.add_parser("train").add_argument("--epochs", type=int, default=40)
    commands.add_parser("promote").add_argument("--version", type=int, required=True)
    commands.add_parser("monitor").add_argument("--hours", type=float, default=1)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, default=str))


def run(args):
    if args.command == "init":
        initialize()
        return {"schema": "ready"}
    if args.command == "seed":
        from .seed import seed

        initialize()
        return seed()
    if args.command == "status":
        with source_connection() as conn:
            return {
                "posts": conn.execute("SELECT count(*) AS n FROM posts").fetchone()["n"],
                "users": conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"],
            }
    if args.command == "simulate":
        from .simulator import simulate

        return simulate(args.users, args.sessions, args.hours, args.shift)
    if args.command == "source-post":
        from .source_demo import change_post

        return change_post(args.post, args.body)
    if args.command == "index":
        from .indexing import index_changes

        return index_changes()
    if args.command == "profile":
        from .profiles import build_user_vector

        vector = build_user_vector(args.user)
        return {"user_id": args.user, "ready": vector is not None}
    if args.command == "candidates":
        from .profiles import build_user_vector
        from .retrieval import retrieve_candidates

        rows = retrieve_candidates(args.user, user_vector=build_user_vector(args.user))
        keys = ("id", "author_id", "similarity", "sources")
        return [{k: row[k] for k in keys} for row in rows]
    if args.command == "train":
        from .trainer import retrain

        return retrain(force=True, epochs=args.epochs)
    if args.command == "baseline":
        from .baseline import baseline

        return baseline(args.user, args.strategy)
    if args.command == "generate":
        from .generation import generate_for_user

        return generate_for_user(args.user)
    if args.command == "models":
        from .registry import versions

        return versions()
    if args.command == "promote":
        from .registry import promote

        return promote(args.version)
    if args.command == "rollback":
        from .registry import rollback

        return rollback()
    if args.command == "monitor":
        from .trainer import monitor

        return monitor(args.hours)
    raise ValueError(args.command)
