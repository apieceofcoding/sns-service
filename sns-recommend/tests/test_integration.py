from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver

from sns_recommend.api import app
from sns_recommend.core.config import settings
from sns_recommend.core.measurement import CallLimitExceeded, measured_call
from sns_recommend.core.types import (
    DatabaseConnection,
    DatabaseRow,
    PausedResult,
    RankingInput,
    RankingResult,
)
from sns_recommend.data.events import Event, accept_event
from sns_recommend.data.indexing import index_posts
from sns_recommend.data.seed import READERS
from sns_recommend.data.source_demo import change_post
from sns_recommend.pipelines.graph import make_graph, run_graph, start_graph
from sns_recommend.providers.embeddings import (
    CachedEmbeddings,
    FixtureEmbeddings,
    normalize,
    space,
    vector_sql,
)
from sns_recommend.recommenders.retrieval import retrieve_candidates, update_profile
from sns_recommend.storage.feeds import publish, read_feed
from sns_recommend.storage.jobs import claim, enqueue, finish, retry
from sns_recommend.storage.postgres import connection, source_connection
from sns_recommend.worker.runner import run_one

pytestmark = pytest.mark.integration
READER = 7  # Seed reader interested in backend and AI. Readers write no posts.


def prepare() -> None:
    index_posts()
    update_profile(READER)


def count(conn: DatabaseConnection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()
    assert row is not None  # COUNT always returns a row.
    return cast(int, row["n"])


def test_event_duplicate_and_old_version_do_not_queue_work(infra: None) -> None:
    event = Event(event_id=uuid4(), kind="post.updated", post_id=1, version=3)
    assert accept_event(event)["accepted"]
    assert accept_event(event)["duplicate"]
    accept_event(event.model_copy(update={"event_id": uuid4(), "version": 2}))
    with connection() as conn:
        assert count(conn, "jobs") == 1


def test_failed_index_job_does_not_block_a_redelivered_event(infra: None) -> None:
    event = Event(event_id=uuid4(), kind="post.updated", post_id=1, version=3)
    accept_event(event)
    with connection() as conn:
        conn.execute("UPDATE jobs SET status='failed'")
    accept_event(event.model_copy(update={"event_id": uuid4()}))
    with connection() as conn:
        pending = conn.execute("SELECT count(*) AS n FROM jobs WHERE status='pending'").fetchone()
    assert pending is not None and pending["n"] == 1


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


def test_source_outbox_commits_with_post(infra: None) -> None:
    assert change_post(1001, "Python")["version"] == 1
    assert change_post(1001, "Python FastAPI")["version"] == 2
    with source_connection() as conn:
        post = conn.execute("SELECT content,content_version FROM posts WHERE id=1001").fetchone()
        events = conn.execute("SELECT event FROM recommend_outbox ORDER BY created_at").fetchall()
        # The app's next generated ID must not collide with the explicit demo ID.
        created = conn.execute(
            """INSERT INTO posts(content,user_id,created_at,modified_at)
            VALUES ('next',1,now(),now()) RETURNING id"""
        ).fetchone()
    assert post == {"content": "Python FastAPI", "content_version": 2}
    assert [(e["event"]["post_id"], e["event"]["version"]) for e in events] == [
        (1001, 1),
        (1001, 2),
    ]
    assert all("body" not in json.dumps(e["event"]) for e in events)
    assert created is not None and created["id"] > 1001


def test_post_event_indexes_the_current_body_from_sns(infra: None) -> None:
    first = change_post(1001, "Python 백엔드")
    accept_event(Event(event_id=uuid4(), kind="post.updated", post_id=1001, version=1))
    assert run_one()
    change_post(1001, "제주 여행 사진")
    # A late copy of the old event adds no work. The new event indexes the new body.
    accept_event(Event(event_id=uuid4(), kind="post.updated", post_id=1001, version=1))
    assert not run_one()
    accept_event(Event(event_id=uuid4(), kind="post.updated", post_id=1001, version=2))
    assert run_one()
    with connection() as conn:
        row = conn.execute(
            "SELECT content_version,embedding::text FROM post_embeddings WHERE post_id=1001"
        ).fetchone()
    assert first["version"] == 1 and row is not None and row["content_version"] == 2
    expected = FixtureEmbeddings().embed_query("제주 여행 사진")
    assert json.loads(row["embedding"]) == pytest.approx(expected, abs=1e-6)


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


def test_exclusions_delete_and_stale_vectors(infra: None) -> None:
    prepare()
    accept_event(Event(event_id=uuid4(), kind="impression", user_id=READER, post_id=200))
    with source_connection() as conn:
        conn.execute(
            "UPDATE posts SET deleted_at=now(),content_version=content_version+1 WHERE id=195"
        )
        conn.execute(
            "UPDATE posts SET content='edited',content_version=content_version+1 WHERE id=190"
        )
    candidates = {p["id"]: p for p in retrieve_candidates(READER, k=50)}
    assert 200 not in candidates and 195 not in candidates
    assert candidates[190]["similarity"] is None
    index_posts([190, 195])
    assert {p["id"]: p for p in retrieve_candidates(READER, k=50)}[190]["similarity"] is not None
    with connection() as conn:
        assert not conn.execute("SELECT 1 FROM post_embeddings WHERE post_id=195").fetchone()


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
    job = claim(("build",), job_id=paused["job_id"])
    assert job is not None
    result = run_graph(job)
    assert result["published"]
    assert len(calls) == 1
    assert read_feed(READER)["snapshot_id"] == paused["job_id"]


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


def test_new_generation_fences_old_graph(infra: None) -> None:
    prepare()
    old = start_graph(READER, pause=True)
    with connection() as conn:
        enqueue(conn, "build", user_id=READER)
    resumed = claim(("build",), job_id=old["job_id"])
    assert resumed is not None
    assert not run_graph(resumed)["published"]
    assert not read_feed(READER)["ready"]


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


def test_lease_ownership_blocks_late_worker(infra: None) -> None:
    prepare()
    with connection() as conn:
        job_id = enqueue(conn, "build", user_id=READER)
    old = claim(("build",), job_id=job_id)
    assert old is not None
    with connection() as conn:
        conn.execute("UPDATE jobs SET owner=%s WHERE id=%s", (uuid4(), job_id))
    with pytest.raises(RuntimeError, match="lease lost"):
        run_graph(old)


def test_lost_owner_cannot_change_saved_checkpoint(infra: None) -> None:
    prepare()
    with connection() as conn:
        job_id = enqueue(conn, "build", user_id=READER)
    old = claim(("build",), job_id=job_id)
    assert old is not None
    assert cast(PausedResult, run_graph(old, pause=True))["paused"]
    current = claim(("build",), job_id=job_id)
    assert current is not None
    config: RunnableConfig = {"configurable": {"thread_id": job_id}}
    with PostgresSaver.from_conn_string(settings().database_url) as saver:
        graph = make_graph(saver)
        before = graph.get_state(config)
        with pytest.raises(RuntimeError, match="lease lost"):
            run_graph(old)
        after = graph.get_state(config)
        assert before.config == after.config
        assert before.values == after.values
    assert run_graph(current)["published"]


def test_crashed_jobs_stop_after_retry_limit(infra: None) -> None:
    with connection() as conn:
        job_id = enqueue(conn, "index", post_id=1)
    for attempt in range(1, 4):
        claimed = claim(("index",), job_id=job_id)
        assert claimed is not None
        assert claimed["attempts"] == attempt
        with connection() as conn:
            conn.execute(
                "UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (job_id,)
            )
    assert claim(("index",), job_id=job_id) is None
    with connection() as conn:
        row = conn.execute("SELECT status,attempts FROM jobs WHERE id=%s", (job_id,)).fetchone()
    assert row == {"status": "failed", "attempts": 3}


def test_retry_does_not_reopen_finished_job(infra: None) -> None:
    with connection() as conn:
        job_id = enqueue(conn, "index", post_id=1)
    job = claim(("index",), job_id=job_id)
    assert job is not None
    finish(job)
    retry(job, "metrics unavailable")
    with connection() as conn:
        assert (
            cast(
                DatabaseRow,
                conn.execute("SELECT status FROM jobs WHERE id=%s", (job_id,)).fetchone(),
            )["status"]
            == "done"
        )


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
                kind="like",
                user_id=READER,
                post_id=i + 1,
                occurred_at=now - timedelta(minutes=i + 1),
            )
        )
    update_profile(READER)
    with connection() as conn:
        row = conn.execute(
            "SELECT embedding::text FROM profiles WHERE user_id=%s", (READER,)
        ).fetchone()
    assert row is not None
    base = FixtureEmbeddings().embed_query(READERS[READER])
    expected = normalize([0.7 * x + 0.3 * y for x, y in zip(base, recent, strict=True)])
    assert json.loads(row["embedding"]) == pytest.approx(expected, abs=1e-7)


def test_stale_user_vector_is_not_used_for_similarity(infra: None) -> None:
    prepare()
    with source_connection() as conn:
        conn.execute("UPDATE user_interests SET interests='음악 감상' WHERE user_id=%s", (READER,))
    candidates = retrieve_candidates(READER)
    assert candidates
    assert all(p["similarity"] is None and "embedding" not in p["sources"] for p in candidates)


def test_new_account_without_interests_gets_latest_and_popular_only(infra: None) -> None:
    index_posts()
    with source_connection() as conn:
        conn.execute(
            """INSERT INTO users(id,username,created_at,modified_at)
            VALUES (10,'signed-up-in-app',now(),now())"""
        )
    update_profile(10)
    candidates = retrieve_candidates(10)
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
    candidates = retrieve_candidates(READER)
    assert len(candidates) == 30
    by_id = {p["id"]: p for p in candidates}
    assert "latest" in by_id[1001]["sources"]
    assert "popular" in by_id[1002]["sources"]


def test_function_generation_rejects_superseded_result_and_labels_replay(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sns_recommend.pipelines.generation import generate

    candidate = {"id": 1, "author_id": 10, "topic": "backend"}
    monkeypatch.setattr(
        "sns_recommend.pipelines.generation.prepare_inputs",
        lambda user_id: {"candidates": [candidate]},
    )

    def supersede(inputs: RankingInput) -> RankingResult:
        with connection() as conn:
            enqueue(conn, "build", user_id=READER)
        return {"ordered_ids": [1], "mode": "replay", "usage": {}}

    monkeypatch.setattr("sns_recommend.pipelines.generation.rerank_candidates", supersede)
    result = generate(READER)
    assert result["strategy"] == "replay_llm"
    assert not result["published"]
    assert not read_feed(READER)["ready"]


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
    ids = {p["id"] for p in retrieve_candidates(READER, k=50, as_of=reference)}
    assert ids == set(range(7, 19))


def test_event_worker_delivers_without_fastapi(infra: None) -> None:
    from sns_recommend.event_worker import poll_once

    change_post(1001, "Python batch")
    assert poll_once() == {"delivered": 1}
    assert poll_once() == {"delivered": 0}
    with connection() as conn:
        assert count(conn, "events") == 1
        assert count(conn, "jobs") == 1
    with source_connection() as conn:
        row = conn.execute("SELECT delivered_at FROM recommend_outbox").fetchone()
        assert row is not None and row["delivered_at"] is not None


def test_event_worker_replays_after_source_ack_transaction_rolls_back(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager

    from sns_recommend import event_worker

    change_post(1001, "Python replay")

    @contextmanager
    def interrupted_source() -> Iterator[DatabaseConnection]:
        with source_connection() as conn:
            yield conn
            raise RuntimeError("source acknowledgement interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(event_worker, "source_connection", interrupted_source)
        with pytest.raises(RuntimeError):
            event_worker.poll_once()
    with source_connection() as conn:
        row = conn.execute("SELECT delivered_at FROM recommend_outbox").fetchone()
        assert row is not None and row["delivered_at"] is None
    assert event_worker.poll_once() == {"delivered": 1}
    with connection() as conn:
        assert count(conn, "events") == 1
        assert count(conn, "jobs") == 1


def test_event_worker_skips_events_locked_by_another_consumer(infra: None) -> None:
    from sns_recommend.event_worker import poll_once

    change_post(1001, "Python locked")
    change_post(1002, "Python free")
    with source_connection() as conn:
        conn.execute("SELECT id FROM recommend_outbox WHERE event->>'post_id'='1001' FOR UPDATE")
        assert poll_once() == {"delivered": 1}
    assert poll_once() == {"delivered": 1}
    with connection() as conn:
        assert count(conn, "events") == 2


def test_event_worker_limits_work_per_poll(infra: None) -> None:
    from sns_recommend.event_worker import poll_once

    change_post(1001, "Python first")
    change_post(1002, "Python second")
    assert poll_once(1) == {"delivered": 1}
    assert poll_once(1) == {"delivered": 1}
    assert poll_once(1) == {"delivered": 0}


def test_event_worker_keeps_outbox_pending_when_event_processing_fails(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sns_recommend import event_worker

    change_post(1001, "Python failed")

    def unavailable(event: Event) -> None:
        raise RuntimeError("recommend database unavailable")

    monkeypatch.setattr(event_worker, "accept_event", unavailable)
    with pytest.raises(RuntimeError):
        event_worker.poll_once()
    with source_connection() as conn:
        row = conn.execute("SELECT delivered_at FROM recommend_outbox").fetchone()
        assert row is not None and row["delivered_at"] is None
    with connection() as conn:
        assert count(conn, "events") == 0
        assert count(conn, "jobs") == 0
