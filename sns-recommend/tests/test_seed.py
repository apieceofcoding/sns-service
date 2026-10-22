from __future__ import annotations

from sns_recommend.data.seed import TOPICS, USERNAMES


def test_course_topics_have_examples() -> None:
    assert len(TOPICS) == 6
    from sns_recommend.post_examples import post_body

    assert all(len(post_body(topic, 0)) > 10 for topic in TOPICS)


def test_seed_users_have_distinct_usernames() -> None:
    assert set(USERNAMES) == set(range(1, 10))
    assert len(set(USERNAMES.values())) == 9


def test_post_examples_are_distinct_and_deterministic() -> None:
    from sns_recommend.post_examples import post_body

    bodies = [post_body(topic, n) for topic in TOPICS for n in range(40)]
    assert len(set(bodies)) == 240
    assert bodies == [post_body(topic, n) for topic in TOPICS for n in range(40)]
    assert all("오늘의 기록" not in body for body in bodies)


def test_seed_dates_cover_window_boundaries_for_every_topic() -> None:
    from collections import Counter
    from datetime import UTC, datetime, timedelta

    from sns_recommend.post_examples import post_created_at

    reference = datetime(2026, 10, 10, 12, tzinfo=UTC)
    dates = {i: post_created_at(i, reference, group_size=6) for i in range(1, 241)}
    assert all(dates[i] == reference - timedelta(hours=48, minutes=1) for i in range(1, 7))
    assert all(dates[i] == reference - timedelta(hours=48) for i in range(7, 13))
    assert all(dates[i] == reference - timedelta(hours=47, minutes=59) for i in range(13, 19))
    assert all(dates[i] == reference + timedelta(minutes=1) for i in range(19, 25))
    eligible = [
        i for i, date in dates.items() if reference - timedelta(hours=48) <= date <= reference
    ]
    assert len(eligible) == 228
    counts = Counter(list(TOPICS)[(i - 1) % 6] for i in eligible)
    assert set(counts.values()) == {38}
