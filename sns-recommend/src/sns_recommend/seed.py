from datetime import UTC, datetime

from sns_recommend.post_examples import post_body, post_created_at

from .db import source_connection

TOPICS = {
    "backend": "Python과 FastAPI로 백엔드 API를 만들고 PostgreSQL 데이터베이스를 튜닝해요",
    "travel": "서울 골목과 제주 바다를 여행하며 사진과 맛집 산책 기록을 남겨요",
    "fitness": "러닝과 근력 운동으로 건강을 챙기고 훈련 기록을 남겨요",
    "ai_dev": "Python으로 LLM, RAG, 임베딩 검색을 붙인 AI 서비스를 개발해요",
    "travel_video": "여행 브이로그를 촬영하고 편집해서 여행 유튜브에 올려요",
    "fitness_food": "운동 식단과 러닝 전후 식사, 주말 밀프렙을 기록해요",
}
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
        for user_id in USERNAMES:
            username = USERNAMES[user_id]
            existing = conn.execute("SELECT username FROM users WHERE id=%s", (user_id,)).fetchone()
            if existing and existing["username"] != username:
                raise ValueError(f"seed user ID {user_id} is already used by another account")
            conn.execute(
                """INSERT INTO users(id,username,created_at,modified_at)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (user_id, username, now, now),
            )

        for i in range(1, 241):
            topic = list(TOPICS)[(i - 1) % 6]
            author_id = 1 + (i - 1) % 6
            body = post_body(topic, (i - 1) // 6)
            existing = conn.execute("SELECT user_id FROM posts WHERE id=%s", (i,)).fetchone()
            if existing and existing["user_id"] != author_id:
                raise ValueError(f"seed post ID {i} conflicts with existing data; use a fresh course database")
            conn.execute(
                """INSERT INTO posts(id,user_id,content,like_count,created_at,modified_at)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (i, author_id, body, (i * 17) % 101, post_created_at(i, now, group_size=6), now),
            )
        advance_identity(conn, "users", "posts")
    return {"users": 9, "posts": 240, "data": "synthetic", "reference_time": now.isoformat()}


def advance_identity(conn, *tables):
    # Explicit IDs must not collide with the app's next generated ID.
    for table in tables:
        conn.execute(f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
            GREATEST((SELECT max(id) FROM {table}),
                     nextval(pg_get_serial_sequence('{table}', 'id'))), true)""")
