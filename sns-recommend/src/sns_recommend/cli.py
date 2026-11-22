import argparse
import json

from .db import initialize, source_connection


def main():
    parser = argparse.ArgumentParser(prog="sns-recommend")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "seed", "status"):
        commands.add_parser(name)
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
    raise ValueError(args.command)
