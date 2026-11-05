"""Reads from the SNS database. Posts and accounts stay there and are never copied."""

from .db import source_connection

# A feed candidate is an original post: not deleted, not a reply and not a repost.
VISIBLE = "deleted_at IS NULL AND parent_id IS NULL AND repost_id IS NULL"


def ordered_post_ids(strategy):
    order = {"latest": "created_at DESC,id DESC", "popular": "like_count DESC,id DESC"}[strategy]
    with source_connection() as conn:
        rows = conn.execute(f"SELECT id FROM posts WHERE {VISIBLE} ORDER BY {order}").fetchall()
    return [row["id"] for row in rows]


def user_exists(user_id):
    with source_connection() as conn:
        return (
            conn.execute(
                "SELECT id FROM users WHERE id=%s AND deleted_at IS NULL", (user_id,)
            ).fetchone()
            is not None
        )


def alive_ids(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM posts WHERE id=ANY(%s) AND deleted_at IS NULL", (post_ids,)
        ).fetchall()
    return {row["id"] for row in rows}


def posts_to_index(post_ids=None):
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,content AS body,content_version AS version,
            ({VISIBLE}) AS visible FROM posts
            WHERE %s::bigint[] IS NULL OR id=ANY(%s) ORDER BY id""",
            (post_ids, post_ids),
        ).fetchall()


def current_versions(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            f"SELECT id,content_version FROM posts WHERE id=ANY(%s) AND {VISIBLE}", (post_ids,)
        ).fetchall()
    return {row["id"]: row["content_version"] for row in rows}


def recent_posts(user_id, reference, hours=48):
    from datetime import timedelta

    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,user_id AS author_id,content AS body,
            content_version AS version,like_count AS likes,
            created_at AT TIME ZONE 'UTC' AS created_at FROM posts
            WHERE {VISIBLE} AND user_id<>%s AND created_at<=%s AND created_at>=%s""",
            (user_id, reference, reference - timedelta(hours=hours)),
        ).fetchall()


def post_bodies(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            "SELECT id,content FROM posts WHERE id=ANY(%s) AND deleted_at IS NULL", (post_ids,)
        ).fetchall()
    return {row["id"]: row["content"] for row in rows}
