import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sns_recommend.api import app
from sns_recommend.feed import publish, read_feed, redis_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("COURSE_REDIS_TESTS") != "1", reason="requires course Redis"),
]


@pytest.fixture
def user():
    user_id = uuid4().int % (2**62) + 1000
    yield user_id
    redis = redis_client()
    keys = list(redis.scan_iter(f"recommend:feed:{user_id}:*"))
    redis.delete(f"recommend:current:{user_id}", *keys)


def test_new_publication_does_not_change_previous_cursor(user):
    publish(user, [3, 1, 2], "latest")
    first = read_feed(user, limit=1)
    publish(user, [2, 1, 3], "popular")
    assert read_feed(user)["post_ids"] == [2, 1, 3]
    previous = read_feed(user, limit=2, cursor=first["next_cursor"])
    assert previous["post_ids"] == [1, 2]
    assert previous["snapshot_id"] == first["snapshot_id"]
    assert previous["next_cursor"] is None
    assert redis_client().ttl(f"recommend:feed:{user}:{first['snapshot_id']}") > 0


def test_feed_api_without_token_and_cursor_errors(user):
    client = TestClient(app)
    assert client.get(f"/internal/feeds/{user}").json()["ready"] is False
    publish(user, [1, 2], "latest")
    response = client.get(f"/internal/feeds/{user}?limit=1")
    assert response.status_code == 200
    first = response.json()
    assert first["post_ids"] == [1]
    cursor = first["next_cursor"]
    assert client.get(f"/internal/feeds/{user + 1}", params={"cursor": cursor}).status_code == 400
    redis_client().delete(f"recommend:feed:{user}:{first['snapshot_id']}")
    assert client.get(f"/internal/feeds/{user}", params={"cursor": cursor}).status_code == 410


def test_empty_snapshot_is_ready(user):
    publish(user, [], "latest")
    response = read_feed(user)
    assert response["ready"] is True
    assert response["post_ids"] == []
    assert response["next_cursor"] is None
