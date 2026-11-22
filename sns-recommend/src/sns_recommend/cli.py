import argparse
import json

from .db import initialize


def main():
    parser = argparse.ArgumentParser(prog="sns-recommend")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "seed"):
        commands.add_parser(name)
    simulate = commands.add_parser("simulate", help="synthetic readers see posts and react")
    simulate.add_argument("--users", type=int, default=300)
    simulate.add_argument("--sessions", type=int, default=15)
    simulate.add_argument("--hours", type=float, default=4)
    simulate.add_argument(
        "--shift", action="store_true", help="from now on readers favor fresh posts far more"
    )
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
    if args.command == "simulate":
        from .simulator import simulate

        return simulate(args.users, args.sessions, args.hours, args.shift)
    raise ValueError(args.command)
