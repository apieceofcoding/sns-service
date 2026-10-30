from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sns_recommend.api import app
from sns_recommend.core.config import settings
from sns_recommend.core.measurement import CallLimitExceeded, measured_call
from sns_recommend.core.types import (
    DatabaseConnection,
    PausedResult,
    RankingInput,
    RankingResult,
)
from event_fixtures import Event, accept_event
from sns_recommend.data.indexing import index_posts
from sns_recommend.data.profiles import build_user_vector
from sns_recommend.data.source_demo import change_post, seed_actions
from sns_recommend.pipelines.graph import run_graph, start_graph
from sns_recommend.providers.embeddings import (
    CachedEmbeddings,
    FixtureEmbeddings,
    space,
    vector_sql,
)
from sns_recommend.recommenders.retrieval import retrieve_candidates
from sns_recommend.storage.event_queue import claim, enqueue, finish, retry
from sns_recommend.storage.feeds import publish, read_feed
from sns_recommend.storage.postgres import connection, source_connection
from sns_recommend.worker.runner import run_one

pytestmark = pytest.mark.integration
READER = 7  # Seed reader interested in backend and AI. Readers write no posts.


def prepare() -> None:
    seed_actions()
    index_posts()


def count(conn: DatabaseConnection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()
    assert row is not None  # COUNT always returns a row.
    return cast(int, row["n"])


def test_recommend_database_keeps_no_copy_of_posts(infra: None) -> None:
    assert index_posts()["indexed"] == 240
    assert index_posts()["indexed"] == 0
    with connection() as conn:
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ).fetchall()
        columns = conn.execute(
            """SELECT column_name FROM information_schema.columns
            WHERE table_name='post_embeddings' ORDER BY column_name"""
        ).fetchall()
        assert count(conn, "post_embeddings") == 240
    assert not {"users", "posts"} & {t["table_name"] for t in tables}
    assert [c["column_name"] for c in columns] == [
        "content_version",
        "embedding",
        "post_id",
        "space",
    ]


def test_post_edited_during_model_call_keeps_no_stale_vector(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    change_post(1001, "Python 백엔드")
    original = CachedEmbeddings.embed_documents

    def edit_while_embedding(self: CachedEmbeddings, texts: list[str]) -> list[list[float]]:
        change_post(1001, "제주 여행 사진")
        return original(self, texts)

    monkeypatch.setattr(CachedEmbeddings, "embed_documents", edit_while_embedding)
    assert index_posts([1001])["indexed"] == 0
    with connection() as conn:
        assert count(conn, "post_embeddings") == 0


def test_old_snapshot_stays_stable_and_publish_is_idempotent(infra: None) -> None:
    assert publish(1, [1, 2, 3, 4], "test", 1, "old", 123.0)
    page = read_feed(1, 2)
    assert publish(1, [4, 3, 2, 1], "test", 2, "new", 124.0)
    assert read_feed(1, 2, page["next_cursor"])["post_ids"] == [3, 4]
    assert publish(1, [4, 3, 2, 1], "test", 2, "new", 124.0)
    assert not publish(1, [1], "test", 1, "stale", 125.0)
    with pytest.raises(ValueError):
        publish(1, [99], "test", 2, "new", 124.0)


def test_graph_resumes_without_repeating_saved_rerank(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare()
    import sns_recommend.pipelines.graph as graph_module

    calls = []
    original = graph_module.rerank_candidates

    def count(inputs: RankingInput) -> RankingResult:
        calls.append(1)
        return original(inputs)

    monkeypatch.setattr(graph_module, "rerank_candidates", count)
    paused = cast(PausedResult, start_graph(READER, pause=True))
    assert paused["next"] == "validate"
    job = claim(("recommend.requested",), event_id=paused["event_id"])
    assert job is not None
    result = run_graph(job)
    assert result["published"]
    assert len(calls) == 1
    assert read_feed(READER)["snapshot_id"] == paused["event_id"]


def test_invalid_rank_uses_rule_branch(infra: None, monkeypatch: pytest.MonkeyPatch) -> None:
    prepare()
    monkeypatch.setattr(
        "sns_recommend.pipelines.graph.rerank_candidates",
        lambda inputs: {"ordered_ids": [99999], "mode": "fixture"},
    )
    result = start_graph(READER)
    assert result["strategy"] == "rules_fallback"
    assert result["published"]
    assert 99999 not in result["post_ids"]


def test_read_api_does_not_call_model(infra: None, monkeypatch: pytest.MonkeyPatch) -> None:
    publish(READER, [1, 2, 3], "latest", 1)

    def forbidden(*args: object) -> Never:
        raise AssertionError("read path called model")

    monkeypatch.setattr("sns_recommend.pipelines.graph.rerank_candidates", forbidden)
    result = TestClient(app).get(f"/internal/feeds/{READER}")
    assert result.status_code == 200
    assert result.json()["post_ids"] == [1, 2, 3]


def test_read_api_skips_posts_deleted_in_sns_and_rejects_unknown_users(infra: None) -> None:
    publish(READER, [1, 2, 3], "latest", 1)
    with source_connection() as conn:
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id=2")
    client = TestClient(app)
    assert client.get(f"/internal/feeds/{READER}").json()["post_ids"] == [1, 3]
    assert client.get("/internal/feeds/999").status_code == 404


def test_budget_is_enforced_before_provider_call(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAILY_CALL_LIMIT", "1")
    from sns_recommend.core.config import settings

    settings.cache_clear()
    calls = []
    measured_call("rerank", "fake", lambda: calls.append(1))
    with pytest.raises(CallLimitExceeded):
        measured_call("rerank", "fake", lambda: calls.append(1))
    assert len(calls) == 1


def test_embedding_record_replays_full_request_from_cold_cache(
    infra: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MODEL_MODE", "record")
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    settings.cache_clear()
    calls = []

    def simulated_provider(self: CachedEmbeddings, texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return FixtureEmbeddings().embed_documents(texts)

    # Synthetic provider data only. This test does not call or record Gemini.
    monkeypatch.setattr(CachedEmbeddings, "_embed_missing", simulated_provider)
    embedding = CachedEmbeddings()
    embedding.embed_documents(["Python"])
    texts = ["Python", "제주 여행", "제주 여행"]
    recorded = embedding.embed_documents(texts)
    assert calls == [["Python"], ["제주 여행"]]
    with connection() as conn:
        conn.execute("DELETE FROM embedding_cache")
    monkeypatch.setenv("MODEL_MODE", "replay")
    settings.cache_clear()
    replayed = embedding.embed_documents(texts)
    for actual, expected in zip(replayed, recorded, strict=True):
        assert actual == pytest.approx(expected)
    assert len(calls) == 2
    # A warm cache must not conceal a missing recording.
    for path in tmp_path.iterdir():
        path.unlink()
    with pytest.raises(FileNotFoundError):
        embedding.embed_documents(texts)


def test_profile_uses_recent_actions_instead_of_largest_post_ids(infra: None) -> None:
    now = datetime.now(UTC)
    recent = [1.0] + [0.0] * 767
    old = [0.0, 1.0] + [0.0] * 766
    with connection() as conn:
        for i in range(7):
            conn.execute(
                """INSERT INTO post_embeddings(post_id,content_version,space,embedding)
                VALUES (%s,1,%s,%s::vector)""",
                (i + 1, space(), vector_sql(recent if i < 5 else old)),
            )
    for i in range(7):
        accept_event(
            Event(
                event_id=uuid4(),
                action="like",
                user_id=READER,
                post_id=i + 1,
                occurred_at=now - timedelta(minutes=i + 1),
            )
        )
    vector = build_user_vector(READER)
    assert vector == pytest.approx(recent, abs=1e-7)


def test_absent_reactions_disable_semantic_search(infra: None) -> None:
    prepare()
    with source_connection() as conn:
        conn.execute(
            "DELETE FROM recommend_events WHERE user_id=%s AND action IN ('like','click')",
            (READER,),
        )
    candidates = retrieve_candidates(READER, user_vector=build_user_vector(READER))
    assert candidates
    assert all(p["similarity"] is None and "embedding" not in p["sources"] for p in candidates)


def test_new_account_without_actions_gets_latest_and_popular_only(infra: None) -> None:
    index_posts()
    with source_connection() as conn:
        conn.execute(
            """INSERT INTO users(id,username,created_at,modified_at)
            VALUES (10,'signed-up-in-app',now(),now())"""
        )
    candidates = retrieve_candidates(10, user_vector=build_user_vector(10))
    assert candidates
    assert all(p["similarity"] is None for p in candidates)
    with pytest.raises(LookupError, match="unknown user"):
        retrieve_candidates(999)


def test_candidate_merge_keeps_fresh_and_popular_posts(infra: None) -> None:
    prepare()
    with source_connection() as conn:
        for post_id, likes in [(1001, 0), (1002, 1_000_000)]:
            conn.execute(
                """INSERT INTO posts(id,user_id,content,like_count,created_at,modified_at)
                VALUES (%s,1,'unindexed',%s,now(),now())""",
                (post_id, likes),
            )
    candidates = retrieve_candidates(READER, user_vector=build_user_vector(READER))
    assert len(candidates) == 30
    by_id = {p["id"]: p for p in candidates}
    assert "latest" in by_id[1001]["sources"]
    assert "popular" in by_id[1002]["sources"]


def test_retrieval_includes_exact_48h_boundary_and_rejects_future(infra: None) -> None:
    from sns_recommend.post_examples import post_created_at

    reference = datetime(2026, 10, 10, 12, tzinfo=UTC)
    with source_connection() as conn:
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id>24")
        for post_id in range(1, 25):
            conn.execute(
                "UPDATE posts SET created_at=%s WHERE id=%s",
                (post_created_at(post_id, reference, group_size=6), post_id),
            )
    prepare()
    ids = {
        p["id"]
        for p in retrieve_candidates(
            READER, user_vector=build_user_vector(READER), k=50, as_of=reference
        )
    }
    assert ids == set(range(7, 19))


def test_source_schema_has_exactly_nine_event_columns(infra: None) -> None:
    with source_connection() as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='recommend_events'"
        ).fetchall()
    assert {r["column_name"] for r in rows} == {
        "id",
        "action",
        "user_id",
        "post_id",
        "version",
        "created_at",
        "claim_id",
        "locked_until",
        "processed_at",
    }
    with connection() as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ).fetchall()
    assert not {"events", "jobs", "exclusions", "posts", "users"} & {r["table_name"] for r in rows}


def test_actual_post_changes_increment_version_and_record_event_atomically(infra: None) -> None:
    with source_connection() as conn:
        conn.execute("UPDATE posts SET content='changed from SNS SQL' WHERE id=1")
        row = conn.execute("SELECT content_version FROM posts WHERE id=1").fetchone()
        assert row["content_version"] == 2
        event = conn.execute("SELECT * FROM recommend_events WHERE post_id=1").fetchone()
        assert event["action"] == "post.updated" and event["version"] == 2
    with pytest.raises(RuntimeError):
        with source_connection() as conn:
            conn.execute("UPDATE posts SET content='rollback' WHERE id=1")
            raise RuntimeError("rollback")
    with source_connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM recommend_events WHERE post_id=1").fetchone()[
                "n"
            ]
            == 1
        )
        conn.execute("UPDATE posts SET like_count=like_count+1 WHERE id=1")
        assert (
            conn.execute("SELECT content_version FROM posts WHERE id=1").fetchone()[
                "content_version"
            ]
            == 2
        )
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id=1")
        assert (
            conn.execute("SELECT content_version FROM posts WHERE id=1").fetchone()[
                "content_version"
            ]
            == 3
        )


def test_event_worker_indexes_only_latest_version_without_api(infra: None) -> None:
    from sns_recommend.event_worker import poll_once

    change_post(1001, "Python old")
    change_post(1001, "Python latest")
    assert poll_once() == {"processed": 2}
    assert poll_once() == {"processed": 0}
    with connection() as conn:
        assert (
            conn.execute(
                "SELECT content_version FROM post_embeddings WHERE post_id=1001"
            ).fetchone()["content_version"]
            == 2
        )
    with source_connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM recommend_events WHERE processed_at IS NOT NULL"
            ).fetchone()["n"]
            == 2
        )


def test_duplicate_action_is_recorded_once_and_remains_available_after_processing(
    infra: None,
) -> None:
    from sns_recommend.event_worker import poll_once

    event = Event(event_id=uuid4(), action="like", user_id=READER, post_id=1)
    assert accept_event(event)["accepted"]
    assert accept_event(event)["duplicate"]
    assert poll_once() == {"processed": 1}
    with source_connection() as conn:
        row = conn.execute(
            "SELECT * FROM recommend_events WHERE id=%s", (event.event_id,)
        ).fetchone()
        assert row["processed_at"] is not None and row["action"] == "like"


def test_failure_remains_retryable_without_an_extra_jobs_table(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sns_recommend import event_worker

    change_post(1001, "Python retry")
    original = event_worker.handle

    def fail(event: object) -> None:
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(event_worker, "handle", fail)
    assert event_worker.poll_once() == {"processed": 0}
    with source_connection() as conn:
        assert (
            conn.execute("SELECT processed_at FROM recommend_events").fetchone()["processed_at"]
            is None
        )
        conn.execute("UPDATE recommend_events SET locked_until=now()-interval '1 second'")
    monkeypatch.setattr(event_worker, "handle", original)
    assert event_worker.poll_once() == {"processed": 1}


def test_old_claim_cannot_acknowledge_or_renew_reclaimed_event(infra: None) -> None:
    from sns_recommend.storage.event_queue import renew

    change_post(1001, "Python claim")
    old = claim(("post.updated",))
    assert old is not None
    assert claim(("post.updated",)) is None
    with source_connection() as conn:
        conn.execute("UPDATE recommend_events SET locked_until=now()-interval '1 second'")
    new = claim(("post.updated",))
    assert new is not None and old["claim_id"] != new["claim_id"]
    assert not finish(old)
    with pytest.raises(RuntimeError):
        renew(old)
    assert finish(new)
    retry(old)
    assert claim(("post.updated",)) is None


def test_vector_commit_before_ack_is_safe_to_repeat(infra: None) -> None:
    from sns_recommend.event_worker import handle, poll_once

    change_post(1001, "Python commit")
    event = claim(("post.updated",))
    assert event is not None
    handle(event)
    with source_connection() as conn:
        conn.execute("UPDATE recommend_events SET locked_until=now()-interval '1 second'")
    assert poll_once() == {"processed": 1}
    with connection() as conn:
        assert count(conn, "post_embeddings") == 1


def test_locked_event_is_skipped_and_each_claim_is_bounded(infra: None) -> None:
    from sns_recommend.event_worker import poll_once

    change_post(1001, "first")
    change_post(1002, "second")
    with source_connection() as conn:
        conn.execute("SELECT * FROM recommend_events WHERE post_id=1001 FOR UPDATE")
        assert poll_once(1) == {"processed": 1}
    assert poll_once(1) == {"processed": 1}


def test_delete_event_removes_vector_without_embedding_call(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sns_recommend.event_worker import poll_once

    index_posts([1])
    with source_connection() as conn:
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id=1")
    monkeypatch.setattr(
        CachedEmbeddings,
        "embed_documents",
        lambda *args: pytest.fail("deleted post called embedding"),
    )
    assert poll_once() == {"processed": 1}
    with connection() as conn:
        assert count(conn, "post_embeddings") == 0


def test_recommend_request_is_deduplicated_until_claimed(infra: None) -> None:
    first = enqueue("recommend.requested", READER)
    assert enqueue("recommend.requested", READER) == first
    event = claim(("recommend.requested",))
    assert event is not None
    assert enqueue("recommend.requested", READER) != first


def test_new_generation_fences_old_graph(infra: None) -> None:
    prepare()
    old = start_graph(READER, pause=True)
    new = start_graph(READER)
    current = claim(("recommend.requested",), event_id=old["event_id"])
    assert current is not None
    assert not run_graph(current)["published"]
    assert read_feed(READER)["snapshot_id"] == new["event_id"]


def test_request_scheduler_and_read_refresh_use_same_event_table(infra: None) -> None:
    from sns_recommend.worker.scheduler import schedule_active

    result = TestClient(app).get(f"/internal/feeds/{READER}")
    assert result.status_code == 200 and result.json()["refresh_event"]
    assert schedule_active() == {"scheduled": 0}
    assert run_one()
    assert read_feed(READER)["ready"]


def test_existing_history_and_work_migrate_without_data_loss(infra: None) -> None:
    from sns_recommend.storage.postgres import initialize

    history_id = uuid4()
    request_id = uuid4()
    with connection() as conn:
        conn.execute(
            "CREATE TABLE events(event_id uuid PRIMARY KEY,kind text,user_id bigint,post_id bigint,occurred_at timestamptz,payload jsonb)"
        )
        conn.execute("INSERT INTO events VALUES (%s,'like',7,1,now(),'{}')", (history_id,))
        conn.execute(
            "CREATE TABLE jobs(id uuid PRIMARY KEY,kind text,user_id bigint,post_id bigint,status text,payload jsonb,created_at timestamptz)"
        )
        conn.execute(
            "INSERT INTO jobs VALUES (%s,'build',7,NULL,'pending','{}',now())", (request_id,)
        )
        conn.execute("CREATE TABLE exclusions(user_id bigint,post_id bigint,reason text)")
        conn.execute("INSERT INTO exclusions VALUES (7,2,'not_interested')")
    initialize()
    initialize()
    with source_connection() as conn:
        row = conn.execute(
            "SELECT action FROM recommend_events WHERE id=%s", (history_id,)
        ).fetchone()
        assert row["action"] == "like"
        row = conn.execute(
            "SELECT action FROM recommend_events WHERE id=%s", (request_id,)
        ).fetchone()
        assert row["action"] == "recommend.requested"
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM recommend_events WHERE action='not_interested'"
            ).fetchone()["n"]
            == 1
        )
    with connection() as conn:
        assert conn.execute("SELECT to_regclass('events') AS name").fetchone()["name"] is None
        assert conn.execute("SELECT to_regclass('jobs') AS name").fetchone()["name"] is None


def test_failed_event_does_not_block_the_next_event(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sns_recommend import event_worker

    change_post(1001, "failed")
    change_post(1002, "healthy")
    original = event_worker.handle

    def handle(event: dict) -> None:
        if event["post_id"] == 1001:
            raise RuntimeError("bad input")
        original(event)

    monkeypatch.setattr(event_worker, "handle", handle)
    assert event_worker.poll_once(2) == {"processed": 1}
    with connection() as conn:
        assert conn.execute("SELECT post_id FROM post_embeddings").fetchone()["post_id"] == 1002


def test_behavior_only_seed_and_cold_start(infra: None) -> None:
    assert seed_actions() == {"actions": 6}
    assert seed_actions() == {"actions": 0}
    index_posts()
    for user in [7, 8, 9]:
        candidates = retrieve_candidates(user, user_vector=build_user_vector(user))
        assert any(p["similarity"] is not None for p in candidates)
    with source_connection() as conn:
        assert (
            conn.execute("SELECT to_regclass('user_interests') AS name").fetchone()["name"] is None
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM information_schema.columns WHERE table_name='users' AND column_name='interests'"
            ).fetchone()["n"]
            == 0
        )


def test_removed_interest_storage_is_cleaned_without_deleting_accounts(infra: None) -> None:
    from sns_recommend.storage.postgres import initialize

    with source_connection() as conn:
        conn.execute("ALTER TABLE users ADD COLUMN interests text")
        conn.execute("CREATE TABLE user_interests(user_id bigint PRIMARY KEY,interests text)")
        conn.execute("INSERT INTO user_interests VALUES (7,'legacy text')")
    initialize()
    initialize()
    with source_connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 9
        assert (
            conn.execute("SELECT to_regclass('user_interests') AS name").fetchone()["name"] is None
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM information_schema.columns WHERE table_name='users' AND column_name='interests'"
            ).fetchone()["n"]
            == 0
        )
