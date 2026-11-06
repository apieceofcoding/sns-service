import pytest

from sns_recommend.ranking import diversify, validate_ranking

CANDIDATES = [
    {"id": 1, "author_id": 1, "topic": "a"},
    {"id": 2, "author_id": 1, "topic": "a"},
    {"id": 3, "author_id": 2, "topic": "b"},
]


@pytest.mark.parametrize("ids", [[1, 2], [1, 2, 99], [1, 1, 3], [True, 2, 3]])
def test_rejects_invalid_model_ids(ids):
    with pytest.raises(ValueError):
        validate_ranking(CANDIDATES, ids)


def test_diversity_preserves_candidates_but_separates_authors():
    assert diversify(CANDIDATES, [1, 2, 3]) == [1, 3, 2]
