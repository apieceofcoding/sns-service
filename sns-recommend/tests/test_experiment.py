from sns_recommend.experiment import arm, compare_rates


def test_groups_are_stable_and_roughly_even() -> None:
    groups = [arm(user_id, "ab-1") for user_id in range(1000)]
    assert groups == [arm(user_id, "ab-1") for user_id in range(1000)]
    assert 400 < groups.count("treatment") < 600
    assert groups != [arm(user_id, "ab-2") for user_id in range(1000)]


def test_click_rate_gap_needs_enough_impressions() -> None:
    small = compare_rates(10, 100, 13, 100)
    large = compare_rates(1000, 10000, 1300, 10000)
    assert small["lift"] == large["lift"] == 0.3
    assert small["p_value"] > 0.05 > large["p_value"]
    assert compare_rates(0, 0, 1, 10) == {"lift": None, "p_value": None}
