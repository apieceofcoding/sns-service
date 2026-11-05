from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from sns_recommend import retrieval

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


def post(post_id, *, age_hours=24, likes=0):
    return {
        "id": post_id,
        "author_id": 1,
        "body": f"post {post_id}",
        "version": 1,
        "likes": likes,
        "created_at": NOW - timedelta(hours=age_hours),
    }


@pytest.fixture
def candidates_from(monkeypatch):
    def run(posts, similarities, *, user_vector=(1.0, 0.0), k=30):
        rows = [
            {"post_id": post_id, "content_version": 1, "similarity": value}
            for post_id, value in similarities.items()
        ]

        class Conn:
            def execute(self, *_):
                return self

            def fetchall(self):
                return rows

        @contextmanager
        def connection():
            yield Conn()

        monkeypatch.setattr(retrieval.source, "user_exists", lambda _: True)
        monkeypatch.setattr(retrieval.source, "recent_posts", lambda *_: posts)
        monkeypatch.setattr(retrieval, "connection", connection)
        monkeypatch.setattr(retrieval, "excluded_ids", lambda _: set())
        monkeypatch.setattr(retrieval, "space", lambda: "test")
        vector = list(user_vector) if user_vector else None
        return retrieval.retrieve_candidates(7, k=k, as_of=NOW, user_vector=vector)

    return run


def test_merge_keeps_fresh_and_popular_when_semantic_fills_k(candidates_from):
    # 1~40 are similar enough to fill k. 101 is the newest, 102 the most liked.
    posts = [post(i, likes=1) for i in range(1, 41)]
    posts += [post(101, age_hours=1), post(102, likes=1000)]
    similarities = {i: 0.9 - i / 100 for i in range(1, 41)} | {101: 0.01, 102: 0.02}

    found = candidates_from(posts, similarities)

    by_id = {p["id"]: p for p in found}
    assert len(found) == 30
    assert "latest" in by_id[101]["sources"]
    assert "popular" in by_id[102]["sources"]
    assert sum("embedding" in p["sources"] for p in found) >= 20


def test_merge_orders_final_candidates_by_similarity(candidates_from):
    posts = [post(i) for i in range(1, 41)]
    found = candidates_from(posts, {i: i / 100 for i in range(1, 41)})

    values = [p["similarity"] for p in found]
    assert values == sorted(values, reverse=True)


def test_merge_without_user_vector_uses_latest_and_popular_only(candidates_from):
    posts = [post(i, age_hours=i, likes=100 - i) for i in range(1, 41)]
    posts.append(post(41, age_hours=47, likes=1000))

    found = candidates_from(posts, {}, user_vector=None)

    assert {p["id"] for p in found} == set(range(1, 11)) | {41}
    assert all(p["similarity"] is None for p in found)
    assert all("embedding" not in p["sources"] for p in found)


def test_merge_returns_every_post_when_fewer_than_k(candidates_from):
    posts = [post(i) for i in range(1, 6)]

    found = candidates_from(posts, {i: 0.5 for i in range(1, 6)})

    assert sorted(p["id"] for p in found) == [1, 2, 3, 4, 5]


def test_merge_respects_small_k(candidates_from):
    posts = [post(i, age_hours=i) for i in range(1, 41)]

    found = candidates_from(posts, {i: i / 100 for i in range(1, 41)}, k=3)

    assert len(found) == 3
