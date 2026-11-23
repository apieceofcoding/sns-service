import os
from collections import Counter

import pytest
from redis import Redis

from sns_recommend.config import settings
from sns_recommend.db import initialize, source_connection
from sns_recommend.seed import AUTHORS, POSTS, USERNAMES, followees, post_fields, seed


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("COURSE_DB_TESTS") != "1", reason="requires an isolated SNS stack")
def test_seed_replaces_all_sns_data_with_fresh_sample_data():
    initialize()
    first = seed()
    with source_connection() as conn:
        conn.execute("INSERT INTO users(username,created_at,modified_at) VALUES ('me',now(),now())")
        before = conn.execute("SELECT id,created_at FROM posts ORDER BY id").fetchall()
    second = seed()
    assert second["reference_time"] > first["reference_time"]
    with source_connection() as conn:
        users = conn.execute("SELECT id,username FROM users ORDER BY id").fetchall()
        posts = conn.execute("SELECT * FROM posts ORDER BY id").fetchall()
        follows = conn.execute("SELECT follower_id,followee_id FROM follows").fetchall()
        media = conn.execute("SELECT id,path FROM media").fetchall()
        assert {u["id"]: u["username"] for u in users} == USERNAMES
        assert Counter(post["user_id"] for post in posts) == dict.fromkeys(AUTHORS, POSTS // 24)
        assert [(p["user_id"], p["content"]) for p in posts] == [
            post_fields(i) for i in range(1, POSTS + 1)
        ]
        assert all(p["created_at"] > b["created_at"] for p, b in zip(posts, before, strict=True))
        assert len(follows) == sum(len(followees(u)) for u in USERNAMES)
        assert len(media) == second["images"] + len(USERNAMES)
        profiles = conn.execute("SELECT profile_media_id FROM users WHERE id=7").fetchone()
        assert media[0]["path"].startswith("seed/profiles/") and profiles["profile_media_id"]
        new_id = conn.execute(
            "INSERT INTO users(username,created_at,modified_at) VALUES ('me',now(),now()) RETURNING id"
        ).fetchone()["id"]
        assert new_id > max(USERNAMES)
    timeline = Redis.from_url(settings().sns_redis_url).zrevrange("timeline:user:7", 0, 0)
    assert int(timeline[0]) in {p["id"] for p in posts if p["user_id"] in followees(7)}
