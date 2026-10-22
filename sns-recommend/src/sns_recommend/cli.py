import argparse
import json

import psycopg
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from .baseline import baseline
from .db import initialize, source_connection
from .seed import seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "seed", "status", "baseline"])
    parser.add_argument("--user", type=int, default=1)
    parser.add_argument("--strategy", choices=["latest", "popular"], default="latest")
    args = parser.parse_args()
    try:
        result = execute(args)
    except psycopg.OperationalError:
        parser.exit(
            1,
            "PostgreSQL 연결 실패: SOURCE_DATABASE_URL을 확인해요.\n"
            "docker compose -f ../sns-app/docker-compose.yml up -d --wait postgres\n",
        )
    except psycopg.errors.UndefinedTable:
        parser.exit(1, "SNS 테이블이 없습니다.\n빈 실습 DB에서 실행: uv run sns-recommend seed\n")
    except (RedisConnectionError, RedisTimeoutError):
        parser.exit(1, "Redis 연결 실패: REDIS_URL을 확인해요.\ndocker compose up -d --wait\n")
    print(json.dumps(result, ensure_ascii=False, default=str))


def execute(args):
    if args.command == "init":
        initialize()
        return {"schema": "ready"}
    if args.command == "seed":
        initialize()
        return seed()
    if args.command == "baseline":
        return baseline(args.user, args.strategy)
    with source_connection() as conn:
        return {
            "posts": conn.execute("SELECT count(*) AS n FROM posts").fetchone()["n"],
            "users": conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"],
        }
