from __future__ import annotations

from typing import Never

import pytest
from fastapi.testclient import TestClient

from sns_recommend.api import app
from sns_recommend.storage.feeds import cursor_decode, cursor_encode


def test_cursor_cannot_move_to_another_user() -> None:
    cursor = cursor_encode(1, "abc", 20)
    assert cursor_decode(cursor, 1) == ("abc", 20)
    with pytest.raises(ValueError):
        cursor_decode(cursor, 2)
    with pytest.raises(ValueError):
        cursor_decode(cursor[:-4] + "AAAA", 1)


def test_feed_rejects_limit_out_of_range() -> None:
    client = TestClient(app)
    assert client.get("/internal/feeds/1?limit=0").status_code == 422


@pytest.mark.parametrize(
    "cursor", ["!", "a" * 513, cursor_encode(1, "abc", True), cursor_encode(1, "../abc", 0)]
)
def test_malformed_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(ValueError, match="invalid cursor"):
        cursor_decode(cursor, 1)


def test_cursor_query_is_bounded_before_storage_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> Never:
        raise AssertionError("invalid cursor reached storage")

    monkeypatch.setattr("sns_recommend.api.routers.feeds.excluded_ids", forbidden)
    response = TestClient(app).get(
        "/internal/feeds/1",
        params={"cursor": "a" * 513},
    )
    assert response.status_code == 422
