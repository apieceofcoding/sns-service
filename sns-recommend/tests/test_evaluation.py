from __future__ import annotations

from pathlib import Path

import pytest

from sns_recommend.evaluation.metrics import ndcg_at_k, recall_at_k
from sns_recommend.evaluation.offline import evaluate


def test_metrics_handle_missing_relevant_posts_and_order() -> None:
    labels = {"1": 1, "2": 1, "3": 0}
    assert recall_at_k([1, 3], labels, 2) == 0.5
    assert ndcg_at_k([1, 2], labels, 2) == 1.0
    assert ndcg_at_k([3, 1], labels, 2) < 1.0
    assert recall_at_k([1], {}, 10) == 0


def test_evaluation_separates_context_from_available_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    from pathlib import Path

    data = json.loads(Path("data/evaluation.json").read_text())
    # An action after cutoff must not leak into the interests used for ranking.
    data["actions"].append(
        {"user_id": 1, "action": "like", "post_id": 2, "at": "2026-10-05T00:00:00+00:00"}
    )
    path = tmp_path / "eval.json"
    path.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)
    expected = evaluate()
    actual = evaluate(str(path))
    assert actual["rows"] == expected["rows"]
    assert len(actual["rows"]) == 12
