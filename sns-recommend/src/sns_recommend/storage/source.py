"""Reads from the SNS database. Posts and accounts stay there and are never copied."""

from __future__ import annotations

from datetime import datetime, timedelta

from sns_recommend.core.types import DatabaseRow
from sns_recommend.storage.postgres import source_connection

# A feed candidate is an original post: not deleted, not a reply and not a repost.
VISIBLE = "deleted_at IS NULL AND parent_id IS NULL AND repost_id IS NULL"
POST = """id,user_id AS author_id,content AS body,content_version AS version,
like_count AS likes,created_at AT TIME ZONE 'UTC' AS created_at"""


def user_exists(user_id: int) -> bool:
    with source_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE id=%s AND deleted_at IS NULL", (user_id,)
        ).fetchone()
    return row is not None


def ordered_post_ids(strategy: str) -> list[int]:
    order = {"latest": "created_at DESC,id DESC", "popular": "like_count DESC,id DESC"}[strategy]
    with source_connection() as conn:
        rows = conn.execute(f"SELECT id FROM posts WHERE {VISIBLE} ORDER BY {order}").fetchall()
    return [row["id"] for row in rows]


def posts_to_index(post_ids: list[int] | None = None) -> list[DatabaseRow]:
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,content AS body,content_version AS version,({VISIBLE}) AS visible
            FROM posts WHERE %s::bigint[] IS NULL OR id=ANY(%s) ORDER BY id""",
            (post_ids, post_ids),
        ).fetchall()


def current_versions(post_ids: list[int]) -> dict[int, int]:
    with source_connection() as conn:
        rows = conn.execute(
            f"SELECT id,content_version FROM posts WHERE id=ANY(%s) AND {VISIBLE}", (post_ids,)
        ).fetchall()
    return {row["id"]: row["content_version"] for row in rows}


def recent_posts(user_id: int, reference: datetime, hours: int = 48) -> list[DatabaseRow]:
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT {POST} FROM posts WHERE {VISIBLE} AND user_id<>%s
            AND created_at<=%s AND created_at>=%s""",
            (user_id, reference, reference - timedelta(hours=hours)),
        ).fetchall()


def alive_ids(post_ids: list[int]) -> set[int]:
    with source_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM posts WHERE id=ANY(%s) AND deleted_at IS NULL", (post_ids,)
        ).fetchall()
    return {row["id"] for row in rows}


def post_bodies(post_ids: list[int]) -> dict[int, str]:
    with source_connection() as conn:
        rows = conn.execute(
            "SELECT id,content FROM posts WHERE id=ANY(%s) AND deleted_at IS NULL", (post_ids,)
        ).fetchall()
    return {row["id"]: row["content"] for row in rows}
