
import pytest
from fastapi.testclient import TestClient

from sns_recommend.api.app import app
from sns_recommend.api.routers import feeds as api


def test_recommend_service_has_no_event_api() -> None:
    assert TestClient(app).post("/internal/events", json={}).status_code == 404


@pytest.mark.parametrize("ready,stale,cursor", [(False, False, None), (True, True, None)])
def test_feed_read_only_reads(
    monkeypatch: pytest.MonkeyPatch, ready: bool, stale: bool, cursor: str | None
) -> None:
    monkeypatch.setattr(api, "excluded_ids", lambda user: set())
    monkeypatch.setattr(api.source, "user_exists", lambda user: True)
    monkeypatch.setattr(
        api,
        "read_feed",
        lambda *a, **kw: {"ready": ready, "stale": stale, "post_ids": [], "next_cursor": cursor},
    )
    response = TestClient(app).get("/internal/feeds/7")
    assert response.status_code == 200
    assert "refresh_event" not in response.json()
    assert not hasattr(api, "enqueue") and not hasattr(api, "connection")
