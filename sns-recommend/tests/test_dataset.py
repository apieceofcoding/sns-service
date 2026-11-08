from datetime import UTC, datetime, timedelta

from sns_recommend.dataset import HISTORY, build_sessions, encode

T0 = datetime(2026, 11, 8, 12, tzinfo=UTC)


def event(post_id, action, minutes, user_id=7):
    return {
        "user_id": user_id,
        "post_id": post_id,
        "action": action,
        "occurred_at": T0 + timedelta(minutes=minutes),
    }


def test_visits_are_split_by_gap_and_history_never_includes_the_future():
    events = [
        event(1, "like", 0),
        event(2, "impression", 10),
        event(3, "impression", 11),
        event(2, "click", 11.5),
        event(4, "impression", 30),
        event(4, "like", 30.5),
    ]
    first, second = build_sessions(events)
    assert first["candidates"] == [2, 3] and first["labels"] == [[1.0, 0.0], [0.0, 0.0]]
    assert [h[0] for h in first["history"]] == [1]
    assert [h[0] for h in second["history"]] == [1, 2]
    assert second["labels"] == [[0.0, 1.0]]


def test_encoding_keeps_the_latest_action_last_and_pads_the_rest():
    features = {i: {"vector": [float(i), 1.0], "created_at": T0} for i in (1, 2, 3)}
    session = {
        "start": T0 + timedelta(hours=2),
        "history": [(1, "like", T0), (2, "click", T0 + timedelta(hours=1))],
        "candidates": [3, 99],  # 99 has no vector and is dropped
        "labels": [[1.0, 0.0], [1.0, 1.0]],
    }
    batch = encode([session], features)
    assert batch["actions"][0, -2:].tolist() == [2, 1]
    assert batch["actions"][0, : HISTORY - 2].sum() == 0
    assert batch["history_age"][0, -1].item() == 1.0
    assert (batch["candidates"][0] > 0).sum() == 1
    assert batch["candidate_age"][0, 0].item() == 2.0
