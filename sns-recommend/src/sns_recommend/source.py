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


def changed_posts(position, limit):
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,content_version AS version,({VISIBLE}) AS visible,
            modified_at AT TIME ZONE 'UTC' AS changed_at,id AS source_id
            FROM posts WHERE (modified_at,id)>(%s::timestamp,%s::bigint)
            ORDER BY modified_at,id LIMIT %s""",
            (*position, limit),
        ).fetchall()


def posts_to_index(post_ids):
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,content AS body,content_version AS version,
            ({VISIBLE}) AS visible FROM posts WHERE id=ANY(%s) ORDER BY id""",
            (post_ids,),
        ).fetchall()


def current_versions(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            f"SELECT id,content_version FROM posts WHERE id=ANY(%s) AND {VISIBLE}", (post_ids,)
        ).fetchall()
    return {row["id"]: row["content_version"] for row in rows}


def recent_posts(user_id, reference, hours=48):
    with source_connection() as conn:
        return conn.execute(
            f"""SELECT id,user_id AS author_id,content AS body,
            content_version AS version,like_count AS likes,
            created_at AT TIME ZONE 'UTC' AS created_at FROM posts
            WHERE {VISIBLE} AND user_id<>%s AND created_at<=%s AND created_at>=%s""",
            (user_id, reference, reference - timedelta(hours=hours)),
        ).fetchall()


def authors(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            "SELECT id,user_id FROM posts WHERE id=ANY(%s)", (list(post_ids),)
        ).fetchall()
    return {row["id"]: row["user_id"] for row in rows}


def created_times(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            f"""SELECT id,content_version,created_at AT TIME ZONE 'UTC' AS created_at
            FROM posts WHERE id=ANY(%s) AND {VISIBLE}""",
            (list(post_ids),),
        ).fetchall()
    return {row["id"]: (row["content_version"], row["created_at"]) for row in rows}
