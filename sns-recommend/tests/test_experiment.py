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
    lucky = compare_readers([(2, 10)] * 40, [(2, 10)] * 39 + [(42, 10)])
    assert steady["lift"] == lucky["lift"] == 0.5
    assert steady["p_value"] < 0.05 < lucky["p_value"]
    assert steady["p_value"] > 0
    assert compare_readers([], [(1, 10)]) == {"lift": None, "p_value": None}


def test_verdict_waits_for_the_planned_size_and_guards_the_like_rate() -> None:
    arms = {"control": {"like_rate": 0.10}, "treatment": {"like_rate": 0.10}}
    better = {"lift": 0.1, "p_value": 0.01}
    assert verdict(arms, better, ready=False).startswith("inconclusive")
    assert verdict(arms, better, ready=True) == "treatment wins"
    assert verdict(arms, {"lift": 0.1, "p_value": 0.2}, ready=True) == "no clear difference"
    assert verdict(arms, {"lift": -0.1, "p_value": 0.01}, ready=True) == "control wins"
    arms["treatment"]["like_rate"] = 0.08
    assert verdict(arms, better, ready=True).startswith("control wins: treatment lowers")


def test_each_group_gets_its_model(monkeypatch: pytest.MonkeyPatch) -> None:
    group = {"experiment": "x", "arm": "treatment", "model": 2}
    monkeypatch.setattr(generation, "retrieve_candidates", lambda user, user_vector: [])
    monkeypatch.setattr(generation, "build_user_vector", lambda user: None)
    monkeypatch.setattr(generation, "assigned", lambda user: group)
    monkeypatch.setattr(
        generation, "rank", lambda user, rows, version: {"ids": [version], "strategy": "model"}
    )
    monkeypatch.setattr(generation, "diversify", lambda rows, ids: ids)
    monkeypatch.setattr(generation, "publish", lambda user, **feed: feed)
    published = generation.generate(7)["published"]
    assert (published["ids"], published["experiment"], published["arm"]) == ([2], "x", "treatment")
