"""Runs against disposable databases only: it deletes every row in the tables it uses."""

import os
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest

from sns_recommend import event_worker
from sns_recommend.data import events, indexing, profiles, source_demo
from sns_recommend.data.seed import seed
from sns_recommend.providers.embeddings import space
from sns_recommend.storage import event_queue, source
from sns_recommend.storage.postgres import connection, initialize, source_connection
from sns_recommend.storage.sync_cursor import load_position

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
        conn.execute("TRUNCATE user_events,post_embeddings,sync_cursors")
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
        conn.execute("UPDATE likes SET deleted_at=now(),modified_at=now() WHERE id=%s", (like_id,))
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


def pending_index() -> list[int]:
    with connection() as conn:
        position = load_position(conn, f"post_index:{space()}")
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
        cursor = conn.execute("SELECT * FROM sync_cursors WHERE name='likes'").fetchone()
    assert cursor["last_id"] == str(like_id)

    with connection() as conn:
        position = load_position(conn, "likes")
    with source_connection() as conn:
        query = event_worker.ACTION_SOURCES[0][2]
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
    monkeypatch.setattr(event_queue, "current_created_at", lambda user_id: None)
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
    monkeypatch.setattr(indexing, "space", lambda: "other-space")
    assert before == 240
    assert indexing.index_changes()["indexed"] > 0


def test_seed_actions_become_events_without_duplicates() -> None:
    assert source_demo.seed_actions() == {"actions": 6}
    assert source_demo.seed_actions() == {"actions": 0}
    event_worker.sync_events()
    assert {r["post_id"] for r in rows("like")} == {1, 4}
    assert len(rows("recommend.requested", 8)) == 1


def test_waiting_request_merges_while_claimed_one_runs() -> None:
    first = event_queue.enqueue(READER)
    assert event_queue.enqueue(READER) == first
    claimed = event_queue.claim(("recommend.requested",))
    assert claimed is not None and event_queue.claim(("recommend.requested",)) is None
    assert event_queue.enqueue(READER) != first
    assert event_queue.finish(claimed)


def test_history_skips_cancelled_likes_and_deleted_posts() -> None:
    from sns_recommend.pipelines import generation as ranking

    keep, cancel = add_like(1), add_like(2)
    with source_connection() as conn:
        conn.execute("UPDATE likes SET deleted_at=now() WHERE id=%s", (cancel,))
    event_worker.poll_once()
    history = ranking.prepare_inputs(READER)["history"]
    assert keep and [row["post_id"] for row in history] == [1]
    assert history[0]["body"]


def test_graph_generates_from_request_and_marks_it_processed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sns_recommend.pipelines import graph

    event_worker.poll_once()
    add_like()
    event_worker.sync_events()
    result = graph.start_graph(READER)
    assert result["published"] is True and result["post_ids"]
    assert rows("recommend.requested")[0]["processed_at"] is not None
