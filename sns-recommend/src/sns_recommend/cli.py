import argparse
import json

from .db import initialize


def main():
    parser = argparse.ArgumentParser(prog="sns-recommend")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "seed"):
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
    raise ValueError(args.command)
