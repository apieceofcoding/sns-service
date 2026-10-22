from datetime import UTC, datetime

from sns_recommend.post_examples import post_body, post_created_at

from .db import source_connection

TOPICS = ("backend", "travel", "fitness", "ai_dev", "travel_video", "fitness_food")
USERNAMES = {
    1: "minjun_dev",
    2: "jiwoo_trip",
    3: "seoyeon_run",
    4: "hyunwoo_ai",
    5: "yuna_vlog",
    6: "dohyun_mealprep",
    7: "jihoon_codes",
    8: "haeun_wander",
    9: "taeyang_fit",
}


def seed():
    now = datetime.now(UTC)
    with source_connection() as conn:
        for user_id, username in USERNAMES.items():
            existing = conn.execute("SELECT username FROM users WHERE id=%s", (user_id,)).fetchone()
            if existing and existing["username"] != username:
                raise ValueError(f"seed user ID {user_id} is already used by another account")
            conn.execute(
                """INSERT INTO users(id,username,created_at,modified_at)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (user_id, username, now, now),
            )

        for i in range(1, 241):
            topic = TOPICS[(i - 1) % len(TOPICS)]
            author_id = 1 + (i - 1) % 6
            body = post_body(topic, (i - 1) // 6)
            existing = conn.execute("SELECT user_id FROM posts WHERE id=%s", (i,)).fetchone()
            if existing and existing["user_id"] != author_id:
                raise ValueError(
                    f"seed post ID {i} conflicts with existing data; use a fresh course database"
                )
            conn.execute(
                """INSERT INTO posts(id,user_id,content,like_count,created_at,modified_at)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (i, author_id, body, (i * 17) % 101, post_created_at(i, now, group_size=6), now),
            )
        for table in ("users", "posts"):
            conn.execute(f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                GREATEST((SELECT max(id) FROM {table}),
                         nextval(pg_get_serial_sequence('{table}', 'id'))), true)""")
    return {"users": 9, "posts": 240, "data": "synthetic", "reference_time": now.isoformat()}
