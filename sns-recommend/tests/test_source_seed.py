"""Run with COURSE_DB_TESTS=1 against an empty, isolated SNS database."""

import os
from collections import Counter

import pytest
from psycopg import sql

from sns_recommend.db import initialize, source_connection
from sns_recommend.post_examples import post_body
from sns_recommend.seed import TOPICS, seed


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("COURSE_DB_TESTS") != "1", reason="requires an isolated SNS database")
def test_seed_uses_only_app_schema_and_preserves_existing_data():
    initialize()
    seed()
    with source_connection() as conn:
        users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        posts = conn.execute("SELECT * FROM posts ORDER BY id").fetchall()
        assert len(users) == 9
        assert len({post["content"] for post in posts}) == 240
        assert Counter(post["user_id"] for post in posts) == {i: 40 for i in range(1, 7)}
        for author, topic in enumerate(TOPICS, 1):
            assert {p["content"] for p in posts if p["user_id"] == author} == {
                post_body(topic, n) for n in range(40)
            }
        for table, rows in (("users", users), ("posts", posts)):
            sequence = conn.execute(
                "SELECT pg_get_serial_sequence(%s, 'id') AS name", (table,)
            ).fetchone()["name"]
            value = conn.execute(
                sql.SQL("SELECT last_value FROM {}").format(sql.Identifier(*sequence.split(".")))
            ).fetchone()["last_value"]
            assert value >= max(row["id"] for row in rows)
    seed()
    with source_connection() as conn:
        assert conn.execute("SELECT * FROM users ORDER BY id").fetchall() == users
        assert conn.execute("SELECT * FROM posts ORDER BY id").fetchall() == posts
