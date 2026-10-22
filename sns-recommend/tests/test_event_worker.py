from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import Mock

import pytest

from sns_recommend import event_worker


def test_empty_batch_opens_no_event_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = []

    @contextmanager
    def source() -> Iterator[Mock]:
        yield conn

    accept = Mock()
    monkeypatch.setattr(event_worker, "source_connection", source)
    monkeypatch.setattr(event_worker, "accept_event", accept)
    assert event_worker.poll_once() == {"delivered": 0}
    accept.assert_not_called()


@pytest.mark.parametrize("size", [0, -1, 1001])
def test_event_worker_rejects_unbounded_queries(size: int) -> None:
    with pytest.raises(ValueError):
        event_worker.poll_once(size)


def test_retry_loop_survives_failure_and_restores_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = Mock()
    stop.is_set.side_effect = [False, False, False, False, True]
    consume = Mock(
        side_effect=[
            RuntimeError("db unavailable"),
            RuntimeError("db unavailable"),
            {"delivered": 1},
            RuntimeError("db unavailable"),
        ]
    )
    previous = Mock()
    handlers = Mock(return_value=previous)
    monkeypatch.setattr(event_worker, "StopEvent", lambda: stop)
    monkeypatch.setattr(event_worker, "poll_once", consume)
    monkeypatch.setattr(event_worker.signal, "signal", handlers)
    event_worker.run_poller()
    assert [call.args[0] for call in stop.wait.call_args_list] == [3, 6, 3, 3]
    assert handlers.call_count == 4
    assert all(call.args[1] is previous for call in handlers.call_args_list[2:])
