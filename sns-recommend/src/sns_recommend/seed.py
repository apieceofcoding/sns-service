from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from redis import Redis

from .config import settings
from .db import clear_tables, source_connection
from .post_examples import post_body, post_created_at

TOPICS = ("backend", "travel", "fitness", "ai_dev", "travel_video", "fitness_food")
POSTS = 1200
IMAGE_EVERY = 7
IMAGES = Path(__file__).parent / "images"
SAMPLE_PASSWORD_HASH = "$argon2id$v=19$m=16384,t=2,p=1$McNMQwbfzzJatCcepcOiUQ$rI/5udC3EkVK/BfDLYDs66iFU8b6cZwKMei9/+wEOzI"
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
READERS = {
    7: ("backend", "ai_dev"),
    8: ("travel", "travel_video"),
    9: ("fitness", "fitness_food"),
    17: ("travel", "fitness"),
    18: ("ai_dev", "travel_video"),
}
AUTHORS = tuple(user_id for user_id in USERNAMES if (user_id - 1) % 10 < len(TOPICS))


def topic_of(author_id: int) -> str:
    return TOPICS[(author_id - 1) % 10]


def post_fields(post_id: int) -> tuple[int, str]:
    group = (post_id - 1) // len(TOPICS)
    author_id = 1 + (post_id - 1) % len(TOPICS) + 10 * (group % 4)
    return author_id, post_body(topic_of(author_id), group)


def followees(user_id: int) -> list[int]:
    if user_id in READERS:
        return [a for a in AUTHORS if topic_of(a) in READERS[user_id]]
    if user_id in AUTHORS:
        return [a for a in AUTHORS if a != user_id and topic_of(a) == topic_of(user_id)]
    return []


def image_of(post_id: int) -> str | None:
    if post_id % IMAGE_EVERY:
        return None
    topic = topic_of(post_fields(post_id)[0])
    return f"seed/{topic}-{post_id // (IMAGE_EVERY * len(TOPICS)) % 4 + 1}.webp"


def seed():
    now = datetime.now(UTC)
    sizes = upload_images()
    media = [
        (i, f"seed/profiles/{name}.webp", uid, sizes[f"seed/profiles/{name}.webp"], now, now)
        for i, (uid, name) in enumerate(USERNAMES.items(), 1)
    ]
    users = [
        (uid, name, SAMPLE_PASSWORD_HASH, i, now, now)
        for i, (uid, name) in enumerate(USERNAMES.items(), 1)
    ]
    follows = [(u, f, now, now) for u in USERNAMES for f in followees(u)]
    posts = []
    for i in range(1, POSTS + 1):
        author_id, content = post_fields(i)
        created_at = post_created_at(i, now)
        image = image_of(i)
        if image:
            media.append((len(media) + 1, image, author_id, sizes[image], created_at, created_at))
        media_ids = [len(media)] if image else None
        posts.append((i, author_id, content, (i * 17) % 101, media_ids, created_at, now))
    with source_connection() as conn:
        clear_tables(conn)
        cursor = conn.cursor()
        cursor.executemany(
            """INSERT INTO users(id,username,password,profile_media_id,created_at,modified_at)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            users,
        )
        cursor.executemany(
            """INSERT INTO follows(follower_id,followee_id,created_at,modified_at)
            VALUES (%s,%s,%s,%s)""",
            follows,
        )
        conn.execute(
            """INSERT INTO follow_counts(user_id,followers_count,followees_count,created_at,
            modified_at) SELECT id,
            (SELECT count(*) FROM follows WHERE followee_id=users.id),
            (SELECT count(*) FROM follows WHERE follower_id=users.id), now(), now() FROM users"""
        )
        cursor.executemany(
            """INSERT INTO media(id,media_type,path,status,user_id,file_size,created_at,modified_at)
            VALUES (%s,'IMAGE',%s,'COMPLETED',%s,%s,%s,%s)""",
            media,
        )
        cursor.executemany(
            """INSERT INTO posts(id,user_id,content,like_count,media_ids,repost_count,reply_count,
            view_count,created_at,modified_at) VALUES (%s,%s,%s,%s,%s,0,0,0,%s,%s)""",
            posts,
        )
        advance_identity(conn, "users", "posts", "media")
    write_timelines(posts)
    return {
        "users": len(users),
        "posts": len(posts),
        "follows": len(follows),
        "images": len(media) - len(users),
        "reference_time": now.isoformat(),
    }


def write_timelines(posts):
    redis = Redis.from_url(settings().sns_redis_url)
    redis.flushdb()
    pipe = redis.pipeline()
    for user_id in USERNAMES:
        shown = {user_id, *followees(user_id)}
        entries = {str(p[0]): p[5].timestamp() * 1000 for p in posts if p[1] in shown}
        if entries:
            pipe.zadd(f"timeline:user:{user_id}", entries)
    pipe.execute()


def upload_images():
    s = settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=s.storage_url,
        aws_access_key_id=s.storage_access_key,
        aws_secret_access_key=s.storage_secret_key.get_secret_value(),
        region_name="ap-northeast-2",
        config=Config(s3={"addressing_style": "path"}),
    )
    try:
        s3.head_bucket(Bucket=s.storage_bucket)
    except ClientError:
        s3.create_bucket(Bucket=s.storage_bucket)
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=s.storage_bucket):
        keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if keys:
            s3.delete_objects(Bucket=s.storage_bucket, Delete={"Objects": keys})
    sizes = {}
    for path in sorted(IMAGES.rglob("*.webp")):
        key = f"seed/{path.relative_to(IMAGES).as_posix()}"
        body = path.read_bytes()
        s3.put_object(Bucket=s.storage_bucket, Key=key, Body=body, ContentType="image/webp")
        sizes[key] = len(body)
    return sizes


def advance_identity(conn, *tables):
    for table in tables:
        conn.execute(f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
            GREATEST((SELECT max(id) FROM {table}),
                     nextval(pg_get_serial_sequence('{table}', 'id'))), true)""")
