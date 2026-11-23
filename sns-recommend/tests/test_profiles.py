from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from sns_recommend import profiles


@pytest.mark.parametrize("mean,expected", [("[1, 1]", [2**-0.5, 2**-0.5]), (None, None)])
def test_user_vector_is_the_normalized_mean_of_recent_posts(
    monkeypatch: pytest.MonkeyPatch, mean: str | None, expected: list[float] | None
) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"mean": mean}
    monkeypatch.setattr(profiles.source, "user_exists", lambda user: True)

    @contextmanager
    def database() -> Iterator[MagicMock]:
        yield conn

    monkeypatch.setattr(profiles, "connection", database)
    result = profiles.build_user_vector(7)
    assert result == (pytest.approx(expected) if expected else None)
    query = conn.execute.call_args.args[0]
    assert "avg(embedding)" in query and "LIMIT 5" in query and "deleted_at IS NULL" in query


def test_unknown_user_cannot_build_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profiles.source, "user_exists", lambda user: False)
    with pytest.raises(LookupError, match="unknown user"):
        profiles.build_user_vector(999)
