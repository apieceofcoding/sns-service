from sns_recommend.evaluation import evaluate, ndcg_at_k, recall_at_k


def test_metrics_handle_missing_relevant_posts_and_order():
    labels = {"1": 1, "2": 1, "3": 0}
    assert recall_at_k([1, 3], labels, 2) == 0.5
    assert ndcg_at_k([1, 2], labels, 2) == 1.0
    assert ndcg_at_k([3, 1], labels, 2) < 1.0
    assert recall_at_k([1], {}, 10) == 0


def test_evaluation_separates_context_from_available_candidates(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    data = json.loads(Path("data/evaluation.json").read_text())
    # An action after cutoff must not leak into the interests used for ranking.
    data["actions"].append(
        {"user_id": 1, "action": "like", "post_id": 2, "at": "2026-10-05T00:00:00+00:00"}
    )
    path = tmp_path / "eval.json"
    path.write_text(json.dumps(data))
    expected = evaluate()
    actual = evaluate(str(path))
    assert actual["rows"] == expected["rows"]
    assert len(actual["rows"]) == 12


def test_evaluation_candidates_use_the_generation_merge_rule(monkeypatch):
    import json
    from datetime import datetime
    from pathlib import Path

    from sns_recommend import evaluation

    seen = []
    original = evaluation.rerank_candidates

    def capture(inputs):
        seen.append(inputs["candidates"])
        return original(inputs)

    monkeypatch.setattr(evaluation, "rerank_candidates", capture)
    evaluate()

    data = json.loads(Path("data/evaluation.json").read_text())
    cutoff = datetime.fromisoformat(data["context_cutoff"])
    observed = datetime.fromisoformat(data["evaluation_time"])
    corpus = [
        p for p in data["posts"] if cutoff < datetime.fromisoformat(p["created_at"]) <= observed
    ]
    newest = max(corpus, key=lambda p: (p["created_at"], p["id"]))["id"]
    most_liked = max(corpus, key=lambda p: (p["likes"], p["id"]))["id"]
    for candidates in seen:
        ids = {p["id"] for p in candidates}
        assert len(candidates) == 30
        assert {newest, most_liked} <= ids
