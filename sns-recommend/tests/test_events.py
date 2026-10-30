from uuid import uuid4
import pytest
from pydantic import ValidationError
from event_fixtures import Event


def test_event_requires_its_target():
    assert Event(event_id=uuid4(), action="post.updated", post_id=3, version=2).version == 2
    with pytest.raises(ValidationError):
        Event(event_id=uuid4(), action="post.updated", version=2)
    with pytest.raises(ValidationError):
        Event(event_id=uuid4(), action="like", user_id=1)


def test_event_never_carries_content():
    # The worker reads the body from the SNS database by post ID.
    with pytest.raises(ValidationError):
        Event.model_validate({"event_id": uuid4(), "action": "post.updated", "post_id": 3,
                              "payload": {"body": "Python"}})


def test_action_api_belongs_to_sns_app():
    from fastapi.testclient import TestClient
    from sns_recommend.api import app

    assert TestClient(app).post("/internal/events", json={}).status_code == 404
