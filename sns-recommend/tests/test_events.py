from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sns_recommend.api import app
from event_fixtures import Event


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


def test_action_ingestion_is_not_exposed_by_recommend_api() -> None:
    assert TestClient(app).post("/internal/events", json={}).status_code == 404
