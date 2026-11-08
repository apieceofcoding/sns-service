import pytest
from fastapi.testclient import TestClient

from sns_recommend.api import app
from sns_recommend.feed import cursor_decode, cursor_encode


def test_cursor_cannot_move_to_another_user():
    cursor = cursor_encode(1, "abc", 20)
    assert cursor_decode(cursor, 1) == ("abc", 20)
    with pytest.raises(ValueError):
        cursor_decode(cursor, 2)
    with pytest.raises(ValueError):
        cursor_decode(cursor[:-4] + "AAAA", 1)


def test_feed_rejects_limit_out_of_range():
    client = TestClient(app)
    assert client.get("/internal/feeds/1?limit=0").status_code == 422
