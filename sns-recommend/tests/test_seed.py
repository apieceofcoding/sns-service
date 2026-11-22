from collections import Counter
from datetime import UTC, datetime, timedelta

from sns_recommend.post_examples import post_created_at
from sns_recommend.seed import AUTHORS, POSTS, TOPICS, USERNAMES, post_fields, topic_of


def test_four_authors_per_topic_five_readers_and_a_newcomer():
    assert len(set(USERNAMES.values())) == len(USERNAMES) == 30
    assert Counter(topic_of(author) for author in AUTHORS) == dict.fromkeys(TOPICS, 4)
    assert set(USERNAMES) - set(AUTHORS) == {7, 8, 9, 17, 18, 19}


def test_every_post_has_its_own_body_and_authors_share_the_work():
    posts = [post_fields(i) for i in range(1, POSTS + 1)]
    assert len({body for _, body in posts}) == POSTS
    assert Counter(author for author, _ in posts) == dict.fromkeys(AUTHORS, POSTS // 24)
    assert post_fields(POSTS + 1)[0] in AUTHORS


def test_each_time_group_contains_all_six_topics():
    reference = datetime(2026, 10, 11, tzinfo=UTC)
    dates = {i: post_created_at(i, reference) for i in range(1, POSTS + 1)}
    recent = [d for d in dates.values() if reference - timedelta(hours=48) <= d <= reference]
    assert len(recent) == POSTS - 12
    for start in (1, 7, 13, 19):
        assert len({dates[i] for i in range(start, start + 6)}) == 1
        assert {topic_of(post_fields(i)[0]) for i in range(start, start + 6)} == set(TOPICS)
