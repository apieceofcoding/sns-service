from collections import Counter
from datetime import UTC, datetime, timedelta

from sns_recommend.seed import TOPICS, USERNAMES
from sns_recommend.post_examples import post_body, post_created_at


def test_author_topics_and_reader_accounts():
    assert len(TOPICS) == 6
    assert set(USERNAMES) == set(range(1,10))
    assert len(set(USERNAMES.values())) == 9
    bodies = [post_body(topic, n) for topic in TOPICS for n in range(40)]
    assert len(set(bodies)) == 240


def test_each_time_group_contains_all_six_topics():
    reference = datetime(2026, 10, 11, tzinfo=UTC)
    dates = {i: post_created_at(i, reference, group_size=6) for i in range(1, 241)}
    assert len([d for d in dates.values() if reference - timedelta(hours=48) <= d <= reference]) == 228
    for start in (1, 7, 13, 19):
        assert len({dates[i] for i in range(start, start + 6)}) == 1
        assert Counter((i - 1) % 6 for i in range(start, start + 6)) == Counter(range(6))
