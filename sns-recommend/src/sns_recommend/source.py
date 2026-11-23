from datetime import timedelta

from .db import source_connection

VISIBLE = "deleted_at IS NULL AND parent_id IS NULL AND repost_id IS NULL"


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


def post_hashes():
    with source_connection() as conn:
        rows = conn.execute(
            f"SELECT id,md5(content) AS hash FROM posts WHERE {VISIBLE} ORDER BY id"
        ).fetchall()
    return {r["id"]: r["hash"] for r in rows}


def post_bodies(post_ids):
    with source_connection() as conn:
        rows = conn.execute("SELECT id,content FROM posts WHERE id=ANY(%s)", (post_ids,)).fetchall()
    return {r["id"]: r["content"] for r in rows}


def recent_posts(user_id, reference, hours=48):
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,user_id AS author_id,content AS body,like_count AS likes,
            created_at AT TIME ZONE 'UTC' AS created_at FROM posts
            WHERE {VISIBLE} AND user_id<>%s AND created_at<=%s AND created_at>=%s""",
            (user_id, reference, reference - timedelta(hours=hours)),
        ).fetchall()


def created_times(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            f"""SELECT id,created_at AT TIME ZONE 'UTC' AS created_at
            FROM posts WHERE id=ANY(%s) AND {VISIBLE}""",
            (list(post_ids),),
        ).fetchall()
    return {r["id"]: r["created_at"] for r in rows}
