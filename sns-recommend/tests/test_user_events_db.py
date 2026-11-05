"""Runs against disposable databases only: it deletes every row in the tables it uses."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from sns_recommend import event_queue, event_worker, events, indexing, profiles, source_demo
from sns_recommend.db import connection, initialize, source_connection
from sns_recommend.seed import seed

pytestmark = pytest.mark.skipif(
    not os.environ.get("SNS_TEST_DISPOSABLE_DB"), reason="needs disposable databases"
)
READER = 7


def rows(action: str, user_id: int = READER) -> list[dict]:
    with connection() as conn:
        return conn.execute(
            "SELECT * FROM user_events WHERE user_id=%s AND action=%s ORDER BY occurred_at",
            (user_id, action),
        ).fetchall()


@pytest.fixture(autouse=True)
def clean(monkeypatch: pytest.MonkeyPatch) -> None:
    initialize()
    with connection() as conn:
        conn.execute("TRUNCATE user_events,post_embeddings")
    with source_connection() as conn:
        conn.execute("TRUNCATE post_actions,likes,posts,users RESTART IDENTITY")
    seed()
    monkeypatch.setattr(event_queue, "current_created_at", lambda user_id: None)


def add_like(post_id: int = 1) -> int:
    now = datetime.now(UTC)
    with source_connection() as conn:
        return conn.execute(
            """INSERT INTO likes(user_id,post_id,created_at,modified_at)
            VALUES (%s,%s,%s,%s) RETURNING id""",
            (READER, post_id, now, now),
        ).fetchone()["id"]


def test_like_is_copied_once_and_cancel_removes_it_from_the_vector() -> None:
    like_id = add_like()
    event_worker.poll_once()
    assert event_worker.sync_events() == 0
    assert [r["source_key"] for r in rows("like")] == [f"like:{like_id}"]
    assert len(rows("recommend.requested")) == 1
    assert profiles.build_user_vector(READER) is not None

    with source_connection() as conn:
        conn.execute("UPDATE likes SET deleted_at=now() WHERE id=%s", (like_id,))
    assert event_worker.sync_events() == 1
    assert rows("like")[0]["removed_at"] is not None
    assert len(rows("recommend.requested")) == 1
    assert profiles.build_user_vector(READER) is None


def test_reply_and_repost_target_the_original_post() -> None:
    now = datetime.now(UTC)
    with source_connection() as conn:
        conn.execute(
            """INSERT INTO posts(content,user_id,parent_id,created_at,modified_at)
            VALUES ('답글',%s,2,%s,%s)""",
            (READER, now, now),
        )
        conn.execute(
            """INSERT INTO posts(content,user_id,repost_id,created_at,modified_at)
            VALUES ('',%s,3,%s,%s)""",
            (READER, now, now),
        )
    event_worker.sync_events()
    assert rows("reply")[0]["post_id"] == 2
    assert rows("repost")[0]["post_id"] == 3


def test_impression_excludes_post_and_click_requests_refresh() -> None:
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(id,user_id,post_id,action) VALUES (%s,%s,5,'impression')",
            (uuid4(), READER),
        )
    event_worker.sync_events()
    assert events.excluded_ids(READER) == {5}
    assert rows("recommend.requested") == []
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(id,user_id,post_id,action) VALUES (%s,%s,6,'click')",
            (uuid4(), READER),
        )
    event_worker.sync_events()
    assert len(rows("click")) == 1
    assert len(rows("recommend.requested")) == 1


def test_recent_impression_schedules_missing_list_with_interval() -> None:
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(id,user_id,post_id,action) VALUES (%s,%s,5,'impression')",
            (uuid4(), READER),
        )
    event_worker.sync_events()
    assert event_queue.schedule_active() == {"scheduled": 1}
    assert event_queue.schedule_active() == {"scheduled": 0}


def test_post_changes_are_indexed_by_version_and_like_count_is_ignored() -> None:
    assert indexing.posts_needing_index()
    event_worker.poll_once()
    assert indexing.posts_needing_index() == []
    with source_connection() as conn:
        conn.execute("UPDATE posts SET like_count=like_count+1 WHERE id=1")
    assert indexing.posts_needing_index() == []
    version = source_demo.change_post(1, "새 본문")["version"]
    assert version == 2 and indexing.posts_needing_index() == [1]
    event_worker.poll_once()
    with source_connection() as conn:
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id=1")
    assert indexing.posts_needing_index() == [1]
    event_worker.poll_once()
    with connection() as conn:
        gone = conn.execute("SELECT 1 FROM post_embeddings WHERE post_id=1").fetchone()
    assert gone is None


def test_seed_actions_become_events_without_duplicates() -> None:
    assert source_demo.seed_actions() == {"actions": 6}
    assert source_demo.seed_actions() == {"actions": 0}
    event_worker.sync_events()
    assert {r["post_id"] for r in rows("like")} == {1, 4}
    assert len(rows("recommend.requested", 8)) == 1
