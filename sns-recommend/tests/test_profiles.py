from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from unittest.mock import MagicMock

import pytest

try:
    profiles = import_module('sns_recommend.data.profiles')
except ModuleNotFoundError:
    profiles = import_module('sns_recommend.profiles')


@pytest.mark.parametrize('case,count', [('mean', 2), ('stale', 0), ('limit', 5)])
def test_user_vector_is_computed_without_state_writes(
    monkeypatch: pytest.MonkeyPatch, case: str, count: int
) -> None:
    size = 7 if case == 'limit' else 2
    conn = MagicMock()
    conn.execute.return_value.fetchall.side_effect = [
        [{'post_id': i} for i in range(size)],
        [
            {'post_id': i, 'content_version': 1, 'embedding': json.dumps([1.0, 0.0] if i % 2 else [0.0, 1.0])}
            for i in range(size)
        ],
    ]
    monkeypatch.setattr(profiles.source, 'user_exists', lambda user: True)
    monkeypatch.setattr(profiles.source, 'current_versions', lambda ids: {i: 2 if case == 'stale' else 1 for i in ids})
    monkeypatch.setattr(profiles, 'space', lambda: 'test:2')
    @contextmanager
    def database() -> Iterator[MagicMock]:
        yield conn
    monkeypatch.setattr(profiles, 'connection', database)
    result = profiles.build_user_vector(7)
    if count:
        assert result is not None
        assert sum(x*x for x in result) == pytest.approx(1.0)
        if case == 'mean':
            assert result == pytest.approx([2**-0.5, 2**-0.5])
        else:
            assert result == pytest.approx([2/(13**0.5), 3/(13**0.5)])
    else:
        assert result is None
    queries = [call.args[0] for call in conn.execute.call_args_list]
    assert all(query.lstrip().startswith('SELECT') for query in queries)
    assert 'GROUP BY post_id' in queries[0] and 'LIMIT 20' in queries[0]
    assert 'removed_at IS NULL' in queries[0]


def test_unknown_user_cannot_build_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profiles.source, 'user_exists', lambda user: False)
    with pytest.raises(LookupError, match='unknown user'):
        profiles.build_user_vector(999)
