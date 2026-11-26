import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from sns_recommend import (
    event_worker,
    events,
    feed,
    generation,
    indexing,
    profiles,
    ranking,
    registry,
    retrieval,
    seed,
    simulator,
    trainer,
    worker,
)
from sns_recommend.db import connection, initialize, source_connection
from sns_recommend.sync_cursor import load_position

pytestmark = pytest.mark.skipif(
    not os.environ.get("SNS_TEST_DISPOSABLE_DB"), reason="needs disposable databases"
)
READER = 7
POSTS = 240


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
        conn.execute("TRUNCATE user_events,post_embeddings,user_event_cursors,simulation")
    monkeypatch.setattr(registry, "MODEL", f"ranker-{uuid4().hex[:8]}")
    with source_connection() as conn:
        conn.execute("TRUNCATE post_actions,likes,posts,users RESTART IDENTITY")
    feed.redis_client().delete(feed.WANTED, f"recommend:current:{READER}")
    monkeypatch.setattr(seed, "POSTS", POSTS)
    seed.seed()


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
    assert rows("like")[0]["deleted_at"] is not None
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


def test_worker_rebuilds_lists_only_for_active_users_without_a_fresh_list() -> None:
    event_worker.drain()
    assert worker.due_users() == []
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(event_id,user_id,post_id,action) VALUES (%s,%s,5,'impression')",
            (uuid4(), READER),
        )
    event_worker.sync_events()
    assert worker.due_users() == [READER]
    assert worker.run_once() == 1
    assert worker.due_users() == []


def test_reading_without_a_list_asks_the_worker_and_expired_cursor_restarts() -> None:
    assert feed.read_feed(READER)["ready"] is False
    assert worker.due_users() == [READER]
    generation.generate(READER)
    first = feed.read_feed(READER, limit=5)
    feed.redis_client().delete(f"recommend:feed:{READER}:{first['snapshot_id']}")
    again = feed.read_feed(READER, limit=5, cursor=first["next_cursor"])
    assert again["post_ids"] == first["post_ids"]


def drain_index() -> None:
    while indexing.index_changes()["indexed"]:
        pass


def test_only_new_or_edited_posts_are_embedded() -> None:
    drain_index()
    with source_connection() as conn:
        conn.execute("UPDATE posts SET like_count=like_count+1 WHERE id=1")
    assert indexing.index_changes()["indexed"] == 0
    with source_connection() as conn:
        conn.execute("UPDATE posts SET content='새 본문' WHERE id=1")
    assert indexing.index_changes()["indexed"] == 1
    with source_connection() as conn:
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id=1")
    indexing.index_changes()
    with connection() as conn:
        gone = conn.execute("SELECT 1 FROM post_embeddings WHERE post_id=1").fetchone()
    assert gone is None


def age_source_rows() -> None:
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
    assert rows("like")[0]["deleted_at"] is not None


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


def test_simulated_readers_become_events_once() -> None:
    result = simulator.simulate(users=5, sessions=3, hours=2)
    assert result["readers"] == len(simulator.READERS) + 5 and result["impressions"] > 0
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


def test_candidate_recall_uses_only_what_was_known_before() -> None:
    simulator.simulate(users=40, sessions=10, hours=3)
    event_worker.drain()
    report = retrieval.candidate_recall(hours=1)
    recall = report["recall@30"]
    assert report["targets"] > 0
    assert all(0 <= value <= 1 for value in recall.values())
    assert recall["candidates"] > recall["random"]


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


def test_history_skips_cancelled_likes() -> None:
    keep, cancel = add_like(1), add_like(2)
    with source_connection() as conn:
        conn.execute("UPDATE likes SET deleted_at=now(),modified_at=now() WHERE id=%s", (cancel,))
    event_worker.poll_once()
    assert keep and [h[0] for h in ranking.recent_history(READER)] == [1]


def test_without_a_model_the_retrieval_order_is_published() -> None:
    event_worker.drain()
    add_like()
    event_worker.sync_events()
    result = generation.generate(READER)
    assert result["published"] is True and result["strategy"] == "embedding"


def test_trained_model_is_registered_promoted_and_served(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(trainer.settings(), "model_dir", str(tmp_path))
    monkeypatch.setattr(trainer, "gate", lambda ndcg: (True, "accepted in this test"))
    simulator.simulate(users=40, sessions=6, hours=3)
    event_worker.drain()
    result = trainer.retrain(force=True, epochs=2)
    assert result["promoted"] is True and registry.active()["id"] == result["version"]
    assert registry.last_run()["outcome"] == "accepted"
    assert trainer.retrain()["trained"] is False
    served = generation.generate(READER)
    assert served["strategy"] == "model" and served["model_version"] == result["version"]
    second = trainer.retrain(force=True, epochs=2)
    registry.promote(second["version"])
    assert registry.rollback() == {"active": result["version"]}
    with pytest.raises(LookupError):
        registry.rollback()


def test_rejected_model_is_logged_but_not_registered(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(trainer.settings(), "model_dir", str(tmp_path))
    monkeypatch.setattr(trainer, "gate", lambda ndcg: (False, "rejected in this test"))
    simulator.simulate(users=40, sessions=6, hours=3)
    event_worker.drain()
    result = trainer.retrain(force=True, epochs=2)
    assert result["promoted"] is False and "version" not in result
    assert registry.last_run()["outcome"] == "rejected" and registry.versions() == []
