from datetime import UTC, datetime

from .db import source_connection
from .post_examples import post_body, post_created_at

TOPICS = ("backend", "travel", "fitness", "ai_dev", "travel_video", "fitness_food")
POSTS = 1200
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
    11: "sangwoo_server",
    12: "nari_backpack",
    13: "junho_lifts",
    14: "eunji_prompt",
    15: "siwoo_films",
    16: "bora_lunchbox",
    17: "sujin_daily",
    18: "minho_weekend",
    19: "arin_firstday",
    21: "kyungmin_db",
    22: "sohee_route",
    23: "daeun_trail",
    24: "woojin_llm",
    25: "chaewon_cut",
    26: "minseo_protein",
    31: "yejun_api",
    32: "harin_hostel",
    33: "seungho_gym",
    34: "jiho_agent",
    35: "yerin_camera",
    36: "hyeri_salad",
}
AUTHORS = tuple(user_id for user_id in USERNAMES if (user_id - 1) % 10 < len(TOPICS))


def topic_of(author_id: int) -> str:
    return TOPICS[(author_id - 1) % 10]


def post_fields(post_id: int) -> tuple[int, str]:
    group = (post_id - 1) // len(TOPICS)
    author_id = 1 + (post_id - 1) % len(TOPICS) + 10 * (group % 4)
    return author_id, post_body(topic_of(author_id), group)


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
        for i in range(1, POSTS + 1):
            author_id, body = post_fields(i)
            existing = conn.execute("SELECT user_id FROM posts WHERE id=%s", (i,)).fetchone()
            if existing and existing["user_id"] != author_id:
                raise ValueError(
                    f"seed post ID {i} conflicts with existing data; use a fresh course database"
                )
            conn.execute(
                """INSERT INTO posts(id,user_id,content,like_count,repost_count,reply_count,
                view_count,created_at,modified_at)
                VALUES (%s,%s,%s,%s,0,0,0,%s,%s) ON CONFLICT DO NOTHING""",
                (i, author_id, body, (i * 17) % 101, post_created_at(i, now, group_size=6), now),
            )
        advance_identity(conn, "users", "posts")
    return {
        "users": len(USERNAMES),
        "posts": POSTS,
        "data": "synthetic",
        "reference_time": now.isoformat(),
    }


def advance_identity(conn, *tables):
    for table in tables:
        conn.execute(f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
            GREATEST((SELECT max(id) FROM {table}),
                     nextval(pg_get_serial_sequence('{table}', 'id'))), true)""")
