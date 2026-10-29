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


@pytest.mark.parametrize('case,expected_count', [('mean', 2), ('stale', 0), ('limit', 5)])
def test_profile_reuses_only_current_post_vectors(
    monkeypatch: pytest.MonkeyPatch, case: str, expected_count: int
) -> None:
    count = 7 if case == 'limit' else 2
    source, vector = MagicMock(), MagicMock()
    source.execute.return_value.fetchall.return_value = [{'post_id': i} for i in range(count)]
    vector.execute.return_value.fetchall.return_value = [
        {'post_id': i, 'content_version': 1, 'embedding': json.dumps([1.0, 0.0] if i % 2 else [0.0, 1.0])}
        for i in range(count)
    ]
    monkeypatch.setattr(profiles.source, 'user_exists', lambda user: True)
    monkeypatch.setattr(profiles.source, 'current_versions', lambda ids: {i: 2 if case == 'stale' else 1 for i in ids})
    monkeypatch.setattr(profiles, 'space', lambda: 'test:2')
    @contextmanager
    def originals() -> Iterator[MagicMock]:
        yield source
    @contextmanager
    def vectors() -> Iterator[MagicMock]:
        yield vector
    monkeypatch.setattr(profiles, 'source_connection', originals)
    monkeypatch.setattr(profiles, 'connection', vectors)
    result = profiles.update_profile(7)
    assert result == {'user_id': 7, 'reaction_posts': expected_count, 'ready': bool(expected_count)}
    parameters = vector.execute.call_args.args[1]
    assert parameters[0] == 7
    if expected_count:
        value = json.loads(parameters[1])
        assert sum(x*x for x in value) == pytest.approx(1.0)
        assert parameters[2] == 'test:2'
        if case == 'mean':
            assert value == pytest.approx([2**-0.5, 2**-0.5])
    else:
        assert parameters[1:] == (None, None)
    query = source.execute.call_args.args[0]
    assert 'GROUP BY post_id' in query and 'LIMIT 20' in query


def test_unknown_user_cannot_create_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profiles.source, 'user_exists', lambda user: False)
    with pytest.raises(LookupError, match='unknown user'):
        profiles.update_profile(999)
