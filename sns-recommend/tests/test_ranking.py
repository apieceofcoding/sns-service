import pytest

from sns_recommend import ranking


def candidates(*authors):
    return [{"id": i + 1, "author_id": a} for i, a in enumerate(authors)]


def test_without_a_model_retrieval_order_is_kept(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ranking, "serving_model", lambda version: (None, None))
    result = ranking.rank(7, candidates(1, 2, 3))
    assert result == {"ids": [1, 2, 3], "strategy": "embedding", "model_version": None}


def test_without_post_features_the_model_is_not_claimed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ranking, "serving_model", lambda version: (object(), 3))
    monkeypatch.setattr(ranking, "recent_history", lambda user: [])
    monkeypatch.setattr(ranking, "post_features", lambda ids: {})
    assert ranking.rank(7, candidates(1, 2))["strategy"] == "embedding"


def test_diversity_spreads_an_author_without_dropping_posts():
    found = ranking.diversify(candidates(1, 1, 1, 2, 3), [1, 2, 3, 4, 5])
    assert sorted(found) == [1, 2, 3, 4, 5]
    assert found[:2] == [1, 2] and found.index(4) < found.index(3)
