from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from sns_recommend import event_worker
from sns_recommend.sync_cursor import next_position


def test_nothing_changed_does_not_call_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(event_worker, "sync_events", lambda: 0)
    monkeypatch.setattr(event_worker, "index_changes", lambda: {"indexed": 0})
    assert event_worker.poll_once() == {"processed": 0, "events": 0, "indexed": 0}


def test_drain_runs_until_nothing_is_left(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(event_worker, "sync_events", Mock(side_effect=[1000, 5, 0]))
    monkeypatch.setattr(event_worker, "index_changes", lambda: {"indexed": 0})
    assert event_worker.drain() == {"processed": 1005, "events": 1005, "indexed": 0}


def test_model_failure_keeps_recorded_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    sync = Mock(return_value=2)
    monkeypatch.setattr(event_worker, "sync_events", sync)
    monkeypatch.setattr(event_worker, "index_changes", Mock(side_effect=RuntimeError("offline")))
    with pytest.raises(RuntimeError):
        event_worker.poll_once()
    sync.assert_called_once()


def test_loop_retries_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = Mock()
    poll = Mock(
        side_effect=[
            RuntimeError("offline"),
            RuntimeError("offline"),
            {"processed": 0},
            KeyboardInterrupt,
        ]
    )
    monkeypatch.setattr(event_worker, "poll_once", poll)
    monkeypatch.setattr(event_worker.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt):
        event_worker.run_poller()
    assert [c.args[0] for c in sleep.call_args_list] == [3, 6, 3]


def test_cursor_keeps_the_overlap_window() -> None:
    settled = datetime(2026, 1, 1, 12, tzinfo=UTC)
    current = (settled - timedelta(hours=1), 5)
    old = {"changed_at": settled - timedelta(minutes=1), "source_id": 9}
    recent = {"changed_at": settled + timedelta(seconds=1), "source_id": 10}
    assert next_position([old], current, settled) == (old["changed_at"], 9)
    assert next_position([old, recent], current, settled) == (settled, 0)
    assert next_position([], current, settled) == (settled, 0)
    assert next_position([recent], (settled + timedelta(seconds=5), 3), settled) == (
        settled + timedelta(seconds=5),
        3,
    )
