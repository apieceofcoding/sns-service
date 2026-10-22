import argparse
import json
from uuid import uuid4
from .events import Event, accept_event
from .db import initialize, source_connection
from .seed import seed
from .baseline import baseline
from .source_demo import change_post
from .indexing import index_posts
from .retrieval import generate_embedding
from .ranking import generate
from .graph import start_graph
from .evaluation import evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "seed", "status", "baseline", "source-post", "action", "index", "embedding", "generate", "graph", "evaluate"])
    parser.add_argument("--user", type=int, default=1)
    parser.add_argument("--strategy", choices=["latest", "popular"], default="latest")
    parser.add_argument("--post", type=int, default=1001)
    parser.add_argument("--body", default="Python PostgreSQL 백엔드 실습")
    parser.add_argument("--pause-after-rerank", action="store_true")
    parser.add_argument("--action", choices=["impression","click","like","not_interested"], default="like")
    args = parser.parse_args()
    if args.command == "init":
        initialize()
        result = {"schema": "ready"}
    elif args.command == "seed":
        initialize()
        result = seed()
    elif args.command == "baseline":
        result = baseline(args.user, args.strategy)
    elif args.command == "action":
        result = accept_event(Event(event_id=uuid4(),action=args.action,user_id=args.user,post_id=args.post))
    elif args.command == "source-post":
        result = change_post(args.post, args.body)
    elif args.command == "index":
        result = index_posts()
    elif args.command == "embedding":
        result = generate_embedding(args.user)
    elif args.command == "generate":
        result = generate(args.user)
    elif args.command == "graph":
        result = start_graph(args.user,args.pause_after_rerank)
    elif args.command == "evaluate":
        result = evaluate()
    else:
        with source_connection() as conn:
            result = {"posts": conn.execute("SELECT count(*) AS n FROM posts").fetchone()["n"],
                      "users": conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]}
    print(json.dumps(result, ensure_ascii=False, default=str))
