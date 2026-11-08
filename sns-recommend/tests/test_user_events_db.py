"""Runs against disposable databases only: it deletes every row in the tables it uses."""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest

from sns_recommend import (
    event_worker,
    events,
    indexing,
    profiles,
    simulator,
    source,
    source_demo,
)
from sns_recommend.db import connection, initialize, source_connection
from sns_recommend.embeddings import embedding_model
from sns_recommend.seed import seed
from sns_recommend.sync_cursor import load_position

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
        conn.execute(
            "TRUNCATE user_events,post_embeddings,user_event_cursors,model_versions,generation_runs"
        )
    with source_connection() as conn:
        conn.execute("TRUNCATE post_actions,likes,posts,users RESTART IDENTITY")
    seed()


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
    assert [r["source_id"] for r in rows("like")] == [like_id]
    assert profiles.build_user_vector(READER) is not None

    with source_connection() as conn:
        conn.execute("UPDATE likes SET deleted_at=now(),modified_at=now() WHERE id=%s", (like_id,))
    assert event_worker.sync_events() == 1
    assert rows("like")[0]["removed_at"] is not None
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


def test_impression_excludes_post_and_click_is_copied() -> None:
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(event_id,user_id,post_id,action) VALUES (%s,%s,5,'impression')",
            (uuid4(), READER),
        )
    event_worker.sync_events()
    assert events.excluded_ids(READER) == {5}
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(event_id,user_id,post_id,action) VALUES (%s,%s,6,'click')",
            (uuid4(), READER),
        )
    event_worker.sync_events()
    assert len(rows("click")) == 1


def pending_index() -> list[int]:
    with connection() as conn:
        position = load_position(conn, f"post_index:{embedding_model()}")
    return indexing.posts_needing_index(source.changed_posts(position, 1000))


def drain_index() -> None:
    while indexing.index_changes()["indexed"]:
        pass


def test_post_changes_are_indexed_by_version_and_like_count_is_ignored() -> None:
    assert pending_index()
    drain_index()
    assert pending_index() == []
    with source_connection() as conn:
        conn.execute("UPDATE posts SET like_count=like_count+1 WHERE id=1")
    assert pending_index() == []
    version = source_demo.change_post(1, "새 본문")["version"]
    assert version == 2 and pending_index() == [1]
    event_worker.poll_once()
    with source_connection() as conn:
        conn.execute("UPDATE posts SET deleted_at=now(),modified_at=now() WHERE id=1")
    assert pending_index() == [1]
    event_worker.poll_once()
    with connection() as conn:
        gone = conn.execute("SELECT 1 FROM post_embeddings WHERE post_id=1").fetchone()
    assert gone is None


def age_source_rows() -> None:
    """Move every row out of the overlap window, as if it changed long ago."""
    with source_connection() as conn:
        conn.execute("UPDATE posts SET modified_at=modified_at-interval '1 hour'")
        conn.execute("UPDATE likes SET modified_at=modified_at-interval '1 hour'")


def test_settled_rows_are_not_read_again_and_late_changes_still_arrive() -> None:
    like_id = add_like()
    age_source_rows()
    assert event_worker.sync_events() == 1
    with connection() as conn:
        cursor = conn.execute("SELECT * FROM user_event_cursors WHERE name='likes'").fetchone()
    assert cursor["last_id"] == like_id

    with connection() as conn:
        position = load_position(conn, "likes")
    with source_connection() as conn:
        query = event_worker.ACTION_SOURCES[0][1]
        assert conn.execute(query, (*position, 10)).fetchall() == []

    with source_connection() as conn:
        conn.execute("UPDATE likes SET deleted_at=now(),modified_at=now() WHERE id=%s", (like_id,))
    assert event_worker.sync_events() == 1
    assert rows("like")[0]["removed_at"] is not None


def test_large_backlog_is_read_in_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(event_worker, "BATCH_SIZE", 2)
    for post_id in (1, 2, 3, 4, 5):
        add_like(post_id)
    age_source_rows()
    assert event_worker.sync_source(*event_worker.ACTION_SOURCES[0]) != []
    assert len(rows("like")) == 2
    while event_worker.sync_source(*event_worker.ACTION_SOURCES[0]):
        pass
    assert len(rows("like")) == 5


def test_model_failure_keeps_the_index_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    age_source_rows()
    monkeypatch.setattr(indexing, "index_posts", Mock(side_effect=RuntimeError("offline")))
    with pytest.raises(RuntimeError):
        indexing.index_changes()
    monkeypatch.undo()
    assert pending_index()[:1] == [1]


def test_rows_past_a_full_batch_in_the_overlap_window_are_reached() -> None:
    drain_index()
    version = source_demo.change_post(240, "새 본문")["version"]
    assert version == 2
    assert indexing.index_changes()["indexed"] == 1


def test_new_embedding_space_indexes_every_post_again(monkeypatch: pytest.MonkeyPatch) -> None:
    drain_index()
    with connection() as conn:
        before = conn.execute("SELECT count(*) AS n FROM post_embeddings").fetchone()["n"]
    monkeypatch.setattr(indexing, "embedding_model", lambda: "other-model")
    assert before == 240
    assert indexing.index_changes()["indexed"] > 0


def test_simulated_readers_become_events_once() -> None:
    result = simulator.simulate(users=5, sessions=3, hours=2)
    assert result["readers"] == 8 and result["impressions"] > 0
    with source_connection() as conn:
        shown = conn.execute(
            "SELECT count(*) AS n FROM post_actions WHERE action='impression'"
        ).fetchone()["n"]
    assert shown == result["impressions"]
    event_worker.drain()
    with connection() as conn:
        copied = conn.execute(
            "SELECT count(*) AS n FROM user_events WHERE action='impression'"
        ).fetchone()["n"]
    assert copied == shown
    assert event_worker.drain()["events"] == 0


def test_late_event_keeps_its_time_and_is_still_copied() -> None:
    event_worker.drain()
    with source_connection() as conn:
        conn.execute(
            """INSERT INTO post_actions(event_id,user_id,post_id,action,created_at)
            VALUES (%s,%s,5,'impression',now()-interval '3 hours')""",
            (uuid4(), READER),
        )
    event_worker.sync_events()
    [late] = rows("impression")
    assert late["occurred_at"] < datetime.now(UTC) - timedelta(hours=2)
