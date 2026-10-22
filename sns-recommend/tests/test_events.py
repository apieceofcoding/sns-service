from __future__ import annotations

from typing import Never
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sns_recommend.api import app
from sns_recommend.data.events import Event


def test_event_requires_its_target() -> None:
    assert Event(event_id=uuid4(), action="post.updated", post_id=3, version=2).version == 2
    with pytest.raises(ValidationError):
        Event(event_id=uuid4(), action="post.updated", version=2)
    with pytest.raises(ValidationError):
        Event(event_id=uuid4(), action="like", user_id=1)


@pytest.mark.parametrize(
    "changes",
    [
        {"post_id": True},
        {"post_id": 2**63},
        {"version": 0},
        {"version": 2**63},
        {"occurred_at": "2026-10-06T12:00:00"},
        # Content never travels in an event. The worker reads it from the SNS database.
        {"payload": {"body": "Python"}},
        {"body": "Python"},
    ],
)
def test_invalid_events_are_rejected(changes: dict[str, object]) -> None:
    event = {"event_id": uuid4(), "action": "post.updated", "post_id": 3, "version": 1}
    with pytest.raises(ValidationError):
        Event.model_validate({**event, **changes})


def test_event_with_content_never_reaches_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> Never:
        raise AssertionError("invalid request reached database")

    monkeypatch.setattr("sns_recommend.api.routers.events.accept_event", forbidden)
    response = TestClient(app).post(
        "/internal/events",

        json={
            "event_id": str(uuid4()),
            "action": "like",
            "post_id": 1,
            "user_id": 1,
            "payload": {"body": "Python"},
        },
    )
    assert response.status_code == 422
