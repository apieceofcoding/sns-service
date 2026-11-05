from unittest.mock import Mock

import pytest

from sns_recommend import event_worker


def test_nothing_changed_does_not_call_model(monkeypatch: pytest.MonkeyPatch) -> None:
    index = Mock()
    monkeypatch.setattr(event_worker, "sync_events", lambda: 0)
    monkeypatch.setattr(event_worker, "schedule_active", lambda: {"scheduled": 0})
    monkeypatch.setattr(event_worker, "posts_needing_index", list)
    monkeypatch.setattr(event_worker, "index_posts", index)
    assert event_worker.poll_once() == {"processed": 0, "events": 0, "indexed": 0, "scheduled": 0}
    index.assert_not_called()


def test_model_failure_keeps_recorded_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    sync = Mock(return_value=2)
    monkeypatch.setattr(event_worker, "sync_events", sync)
    monkeypatch.setattr(event_worker, "schedule_active", lambda: {"scheduled": 0})
    monkeypatch.setattr(event_worker, "posts_needing_index", lambda: [1])
    monkeypatch.setattr(event_worker, "index_posts", Mock(side_effect=RuntimeError("offline")))
    with pytest.raises(RuntimeError):
        event_worker.poll_once()
    sync.assert_called_once()


def test_loop_retries_and_restores_signal_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = Mock()
    stop.is_set.side_effect = [False, False, False, True]
    poll = Mock(side_effect=[RuntimeError("offline"), RuntimeError("offline"), {"processed": 0}])
    handlers = Mock(return_value=None)
    monkeypatch.setattr(event_worker, "Event", lambda: stop)
    monkeypatch.setattr(event_worker, "poll_once", poll)
    monkeypatch.setattr(event_worker.signal, "signal", handlers)
    event_worker.run_poller()
    assert [c.args[0] for c in stop.wait.call_args_list] == [3, 6, 3]
    assert handlers.call_count == 4
