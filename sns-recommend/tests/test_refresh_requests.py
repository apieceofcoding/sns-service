from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from unittest.mock import MagicMock, Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

try:
    api = import_module("sns_recommend.api.routers.feeds")
    queue = import_module("sns_recommend.storage.event_queue")
    app = import_module("sns_recommend.api").app
except ModuleNotFoundError:
    api = import_module("sns_recommend.api")
    queue = import_module("sns_recommend.event_queue")
    app = api.app
worker = import_module("sns_recommend.event_worker")


@contextmanager
def database() -> Iterator[MagicMock]:
    yield MagicMock()


@pytest.fixture
def feed_request(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Mock]:
    monkeypatch.setattr(api, "connection", database)
    monkeypatch.setattr(api, "excluded_ids", lambda user: set())
    monkeypatch.setattr(api.source, "user_exists", lambda user: True)
    reserve = Mock(return_value="refresh-id")
    monkeypatch.setattr(api, "enqueue", reserve)
    return TestClient(app), reserve


@pytest.mark.parametrize(
    "ready,stale,cursor,reserved",
    [
        (False, False, None, True),
        (True, True, "next-page", True),
        (True, False, None, True),
        (True, False, "next-page", False),
    ],
)
def test_feed_reserves_refresh_without_waiting_for_generation(
    monkeypatch: pytest.MonkeyPatch,
    feed_request: tuple[TestClient, Mock],
    ready: bool,
    stale: bool,
    cursor: str | None,
    reserved: bool,
) -> None:
    client, reserve = feed_request
    monkeypatch.setattr(
        api,
        "read_feed",
        lambda *a, **kw: {
            "ready": ready,
            "stale": stale,
            "post_ids": [4] if ready else [],
            "next_cursor": cursor,
        },
    )
    response = client.get("/internal/feeds/7")
    assert response.status_code == 200
    assert response.json()["post_ids"] == ([4] if ready else [])
    if reserved:
        reserve.assert_called_once_with("recommend.requested", 7, throttle=True)
        assert response.json()["refresh_event"] == "refresh-id"
    else:
        reserve.assert_not_called()
        assert "refresh_event" not in response.json()


def test_unknown_user_does_not_reserve_refresh(
    monkeypatch: pytest.MonkeyPatch, feed_request: tuple[TestClient, Mock]
) -> None:
    client, reserve = feed_request
    monkeypatch.setattr(api.source, "user_exists", lambda user: False)
    monkeypatch.setattr(
        api,
        "read_feed",
        lambda *a, **kw: {
            "ready": False,
            "post_ids": [],
            "next_cursor": None,
        },
    )
    assert client.get("/internal/feeds/999").status_code == 404
    reserve.assert_not_called()


def test_queue_failure_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch, feed_request: tuple[TestClient, Mock]
) -> None:
    client, reserve = feed_request
    monkeypatch.setattr(
        api,
        "read_feed",
        lambda *a, **kw: {
            "ready": False,
            "post_ids": [],
            "next_cursor": None,
        },
    )
    reserve.side_effect = psycopg.OperationalError("unavailable")
    assert client.get("/internal/feeds/7").status_code == 503


@pytest.mark.parametrize(
    "action,reserved",
    [
        ("click", True),
        ("like", True),
        ("impression", False),
        ("not_interested", False),
    ],
)
def test_action_worker_only_reserves_for_positive_reactions(
    monkeypatch: pytest.MonkeyPatch, action: str, reserved: bool
) -> None:
    reserve = Mock()
    monkeypatch.setattr(worker, "enqueue", reserve)
    worker.handle({"action": action, "user_id": 7, "post_id": 4})
    if reserved:
        reserve.assert_called_once_with("recommend.requested", 7)
    else:
        reserve.assert_not_called()
    assert "recommend.requested" not in worker.ACTIONS


def test_enqueue_reuses_pending_request(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [None, {"id": "pending-id"}]

    @contextmanager
    def connect() -> Iterator[MagicMock]:
        yield conn

    monkeypatch.setattr(queue, "source_connection", connect)
    assert queue.enqueue("recommend.requested", 7) == "pending-id"
    assert "pg_advisory_xact_lock" in conn.execute.call_args_list[0].args[0]
    assert "ON CONFLICT DO NOTHING" in conn.execute.call_args_list[1].args[0]


def test_enqueue_throttles_recent_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"id": "recent-id"}

    @contextmanager
    def connect() -> Iterator[MagicMock]:
        yield conn

    monkeypatch.setattr(queue, "source_connection", connect)
    assert queue.enqueue("recommend.requested", 7, throttle=True) is None
    assert len(conn.execute.call_args_list) == 2
    assert conn.execute.call_args_list[1].args[1][-1] == 60


def test_periodic_policy_skips_recent_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles, events = MagicMock(), MagicMock()
    profiles.execute.return_value.fetchall.return_value = [{"user_id": 7}, {"user_id": 8}]
    events.execute.return_value.fetchone.side_effect = [{"id": "recent-id"}, None]

    @contextmanager
    def connect_profiles() -> Iterator[MagicMock]:
        yield profiles

    @contextmanager
    def connect_events() -> Iterator[MagicMock]:
        yield events

    monkeypatch.setattr(queue, "connection", connect_profiles)
    monkeypatch.setattr(queue, "source_connection", connect_events)
    reserve = Mock(return_value="refresh-id")
    monkeypatch.setattr(queue, "enqueue", reserve)
    assert queue.schedule_active() == {"scheduled": 1}
    reserve.assert_called_once_with("recommend.requested", 8, throttle=True)
    assert "interval '30 minutes'" in profiles.execute.call_args.args[0]
