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


def created_times(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            f"""SELECT id,content_version,created_at AT TIME ZONE 'UTC' AS created_at
            FROM posts WHERE id=ANY(%s) AND {VISIBLE}""",
            (list(post_ids),),
        ).fetchall()
    return {row["id"]: (row["content_version"], row["created_at"]) for row in rows}
