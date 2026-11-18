import pytest

from sns_recommend import generation
from sns_recommend.experiment import arm, compare_readers, verdict


def test_groups_are_stable_and_roughly_even() -> None:
    groups = [arm(user_id, "ab-1") for user_id in range(1000)]
    assert groups == [arm(user_id, "ab-1") for user_id in range(1000)]
    assert 400 < groups.count("treatment") < 600
    assert groups != [arm(user_id, "ab-2") for user_id in range(1000)]


def test_the_same_gap_convinces_only_when_most_readers_show_it() -> None:
    steady = compare_readers([(2, 10)] * 40, [(3, 10)] * 40)
    # Same totals, but one heavy clicker carries the treatment group.
    lucky = compare_readers([(2, 10)] * 40, [(2, 10)] * 39 + [(42, 10)])
    assert steady["lift"] == lucky["lift"] == 0.5
    assert steady["p_value"] < 0.05 < lucky["p_value"]
    assert steady["p_value"] > 0
    assert compare_readers([], [(1, 10)]) == {"lift": None, "p_value": None}


def test_verdict_waits_for_the_planned_size_and_guards_the_like_rate() -> None:
    arms = {"control": {"like_rate": 0.10}, "treatment": {"like_rate": 0.10}}
    better = {"lift": 0.1, "p_value": 0.01}
    assert verdict(arms, better, ready=False).startswith("wait")
    assert verdict(arms, better, ready=True) == "treatment wins"
    assert verdict(arms, {"lift": 0.1, "p_value": 0.2}, ready=True) == "no clear difference"
    assert verdict(arms, {"lift": -0.1, "p_value": 0.01}, ready=True) == "control wins"
    arms["treatment"]["like_rate"] = 0.08
    assert verdict(arms, better, ready=True).startswith("control wins: treatment lowers")


def candidates() -> list[dict]:
    return [{"id": i, "author_id": 1} for i in (1, 2, 3)]


def patch(monkeypatch: pytest.MonkeyPatch, explore_rate: float, group: dict | None) -> None:
    monkeypatch.setattr(generation.settings(), "explore_rate", explore_rate)
    monkeypatch.setattr(generation, "assigned", lambda user_id: group)
    monkeypatch.setattr(
        generation, "rank", lambda user, rows, version: {"ids": [3, 2, 1], "strategy": "model"}
    )
    monkeypatch.setattr(generation, "diversify", lambda rows, ids: ["spread", *ids])


def test_explore_feed_is_shuffled_and_belongs_to_no_group(monkeypatch) -> None:
    patch(monkeypatch, 1.0, {"experiment": "x", "arm": "control", "model": 1, "spread": True})
    result = generation.order(7, candidates())
    assert result["strategy"] == "explore" and sorted(result["ids"]) == [1, 2, 3]
    assert "arm" not in result


def test_each_group_gets_its_model_and_its_spreading(monkeypatch) -> None:
    patch(monkeypatch, 0.0, {"experiment": "x", "arm": "treatment", "model": 2, "spread": False})
    assert generation.order(7, candidates()) == {
        "ids": [3, 2, 1],
        "strategy": "model",
        "experiment": "x",
        "arm": "treatment",
    }
    patch(monkeypatch, 0.0, {"experiment": "x", "arm": "control", "model": None, "spread": True})
    result = generation.order(7, candidates())
    assert (result["ids"], result["strategy"]) == (["spread", 1, 2, 3], "embedding")
    patch(monkeypatch, 0.0, None)
    assert generation.order(7, candidates())["ids"] == ["spread", 3, 2, 1]
