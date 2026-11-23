from .db import source_connection

VISIBLE = "deleted_at IS NULL AND parent_id IS NULL AND repost_id IS NULL"


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


def created_times(post_ids):
    with source_connection() as conn:
        rows = conn.execute(
            f"""SELECT id,created_at AT TIME ZONE 'UTC' AS created_at
            FROM posts WHERE id=ANY(%s) AND {VISIBLE}""",
            (list(post_ids),),
        ).fetchall()
    return {r["id"]: r["created_at"] for r in rows}
