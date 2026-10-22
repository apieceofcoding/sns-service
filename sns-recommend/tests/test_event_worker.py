from unittest.mock import Mock

import pytest

from sns_recommend import event_worker


def test_empty_queue_does_not_call_model(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = Mock()
    monkeypatch.setattr(event_worker, "claim", lambda actions: None)
    monkeypatch.setattr(event_worker, "handle", handler)
    assert event_worker.poll_once() == {"processed": 0}
    handler.assert_not_called()


@pytest.mark.parametrize("size", [0, -1, 1001])
def test_bounded_poll(size: int) -> None:
    with pytest.raises(ValueError):
        event_worker.poll_once(size)


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
