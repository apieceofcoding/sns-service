import argparse
import json
from datetime import UTC, datetime

from .db import initialize, source_connection


def main():
    parser = argparse.ArgumentParser(prog="sns-recommend")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "seed", "status", "models", "rollback"):
        commands.add_parser(name)
    simulate = commands.add_parser("simulate", help="synthetic readers see posts and react")
    simulate.add_argument("--users", type=int, default=300)
    simulate.add_argument("--sessions", type=int, default=15)
    simulate.add_argument("--hours", type=float, default=4)
    simulate.add_argument(
        "--shift", action="store_true", help="from now on readers favor fresh posts far more"
    )
    post = commands.add_parser("source-post", help="create or edit a post in the SNS database")
    post.add_argument("--post", type=int, default=1001)
    post.add_argument("--body", default="Python PostgreSQL 백엔드 실습")
    for name in ("profile", "candidates", "generate", "benchmark"):
        commands.add_parser(name).add_argument("--user", type=int, default=7)
    commands.add_parser("recall").add_argument("--hours", type=float, default=1)
    commands.add_parser("train").add_argument("--epochs", type=int, default=40)
    commands.add_parser("promote").add_argument("--version", type=int, required=True)
    commands.add_parser("monitor").add_argument("--hours", type=float, default=1)
    experiment = commands.add_parser("experiment", help="A/B test: serving model vs candidate")
    experiment.add_argument("action", choices=["start", "run", "report", "stop"])
    experiment.add_argument("--name", help="default: exp-<month day hour minute>")
    experiment.add_argument(
        "--no-spread", action="store_true", help="treatment: same model, no author spreading"
    )
    experiment.add_argument("--min-impressions", type=int, default=3000, help="per group")
    experiment.add_argument("--rounds", type=int, default=3)
    experiment.add_argument("--users", type=int, default=300)
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
    if args.command == "recall":
        from .retrieval import candidate_recall

        return candidate_recall(args.hours)
    if args.command == "train":
        from .trainer import retrain

        return retrain(force=True, epochs=args.epochs)
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
    if args.command == "experiment":
        from . import experiment

        if args.action == "start":
            name = args.name or f"exp-{datetime.now(UTC):%m%d-%H%M}"
            return experiment.start(name, not args.no_spread, args.min_impressions)
        if args.action == "run":
            return experiment.simulate_feed(args.rounds, args.users)
        if args.action == "stop":
            return experiment.stop()
        return experiment.report()
    from .benchmark import benchmark

    return benchmark(args.user)
