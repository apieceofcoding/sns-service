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
from sns_recommend.data.indexing import index_changes, index_posts
from sns_recommend.data.profiles import build_user_vector
from sns_recommend.data.source_demo import change_post, seed_actions
from sns_recommend.event_worker import poll_once, sync_events
from sns_recommend.pipelines.graph import run_graph, start_graph
from sns_recommend.providers.embeddings import (
    ModelEmbeddings,
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


def index_all() -> int:
    total = 0
    while indexed := index_changes()["indexed"]:
        total += indexed
    return total


def prepare() -> None:
    seed_actions()
    sync_events()
    index_all()


def count(conn: DatabaseConnection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()
    assert row is not None  # COUNT always returns a row.
    return cast(int, row["n"])


def test_recommend_database_keeps_no_copy_of_posts(infra: None) -> None:
    assert index_all() == 240
    assert index_all() == 0
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
    original = ModelEmbeddings.embed_documents

    def edit_while_embedding(self: ModelEmbeddings, texts: list[str]) -> list[list[float]]:
        change_post(1001, "제주 여행 사진")
        return original(self, texts)

    monkeypatch.setattr(ModelEmbeddings, "embed_documents", edit_while_embedding)
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


def test_embedding_record_replays_full_request(
    infra: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MODEL_MODE", "record")
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    settings.cache_clear()
    calls = []

    def simulated_provider(self: ModelEmbeddings, texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return FixtureEmbeddings().embed_documents(texts)

    # Synthetic provider data only. This test does not call or record a model.
    monkeypatch.setattr(ModelEmbeddings, "_embed", simulated_provider)
    embedding = ModelEmbeddings()
    texts = ["Python", "제주 여행"]
    recorded = embedding.embed_documents(texts)
    assert calls == [texts]
    monkeypatch.setenv("MODEL_MODE", "replay")
    settings.cache_clear()
    replayed = embedding.embed_documents(texts)
    for actual, expected in zip(replayed, recorded, strict=True):
        assert actual == pytest.approx(expected)
    assert len(calls) == 1
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
    with source_connection() as conn:
        for i in range(7):
            at = now - timedelta(minutes=i + 1)
            conn.execute(
                "INSERT INTO likes(user_id,post_id,created_at,modified_at) VALUES (%s,%s,%s,%s)",
                (READER, i + 1, at, at),
            )
    sync_events()
    vector = build_user_vector(READER)
    assert vector == pytest.approx(recent, abs=1e-7)


def test_absent_reactions_disable_semantic_search(infra: None) -> None:
    prepare()
    with connection() as conn:
        conn.execute(
            "DELETE FROM user_events WHERE user_id=%s AND action IN ('like','click')",
            (READER,),
        )
    candidates = retrieve_candidates(READER, user_vector=build_user_vector(READER))
    assert candidates
    assert all(p["similarity"] is None and "embedding" not in p["sources"] for p in candidates)


def test_new_account_without_actions_gets_latest_and_popular_only(infra: None) -> None:
    index_all()
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


def test_recommend_database_keeps_one_event_table(infra: None) -> None:
    with connection() as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='user_events'"
        ).fetchall()
        assert {r["column_name"] for r in rows} == {
            "id",
            "user_id",
            "post_id",
            "action",
            "occurred_at",
            "source_key",
            "removed_at",
            "processed_at",
            "claim_id",
            "locked_until",
        }
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ).fetchall()
    assert not {"events", "jobs", "exclusions", "embedding_cache", "posts", "users"} & {
        r["table_name"] for r in rows
    }


def test_actual_post_changes_increment_version(infra: None) -> None:
    def version(conn: DatabaseConnection) -> int:
        return conn.execute("SELECT content_version FROM posts WHERE id=1").fetchone()[
            "content_version"
        ]

    with source_connection() as conn:
        conn.execute("UPDATE posts SET content='changed from SNS SQL' WHERE id=1")
        assert version(conn) == 2
        conn.execute("UPDATE posts SET like_count=like_count+1 WHERE id=1")
        assert version(conn) == 2
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id=1")
        assert version(conn) == 3


def test_event_worker_indexes_only_latest_version_without_api(infra: None) -> None:
    index_all()
    change_post(1001, "Python old")
    change_post(1001, "Python latest")
    assert poll_once()["indexed"] == 1
    assert poll_once()["processed"] == 0
    with connection() as conn:
        assert (
            conn.execute(
                "SELECT content_version FROM post_embeddings WHERE post_id=1001"
            ).fetchone()["content_version"]
            == 2
        )


def test_action_is_copied_once_and_stays_as_history(infra: None) -> None:
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(id,user_id,post_id,action) VALUES (%s,%s,1,'click')",
            (uuid4(), READER),
        )
    assert sync_events() == 1
    assert sync_events() == 0
    with connection() as conn:
        row = conn.execute("SELECT * FROM user_events WHERE action='click'").fetchone()
        assert row["user_id"] == READER and row["removed_at"] is None


def test_failed_indexing_is_read_again_from_the_same_cursor(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_all()
    change_post(1001, "Python retry")

    def fail(self: ModelEmbeddings, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(ModelEmbeddings, "embed_documents", fail)
    with pytest.raises(RuntimeError):
        poll_once()
    monkeypatch.undo()
    assert poll_once()["indexed"] == 1


def test_old_claim_cannot_acknowledge_or_renew_reclaimed_event(infra: None) -> None:
    from sns_recommend.storage.event_queue import renew

    enqueue(READER)
    old = claim(("recommend.requested",))
    assert old is not None
    assert claim(("recommend.requested",)) is None
    with connection() as conn:
        conn.execute("UPDATE user_events SET locked_until=now()-interval '1 second'")
    new = claim(("recommend.requested",))
    assert new is not None and old["claim_id"] != new["claim_id"]
    assert not finish(old)
    with pytest.raises(RuntimeError):
        renew(old)
    assert finish(new)
    retry(old)
    assert claim(("recommend.requested",)) is None


def test_locked_request_is_skipped(infra: None) -> None:
    enqueue(READER)
    with connection() as conn:
        conn.execute("SELECT * FROM user_events WHERE user_id=%s FOR UPDATE", (READER,))
        assert claim(("recommend.requested",)) is None
    assert claim(("recommend.requested",)) is not None


def test_deleted_post_removes_vector_without_embedding_call(
    infra: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    index_all()
    with source_connection() as conn:
        conn.execute("UPDATE posts SET deleted_at=now() WHERE id=1")
    monkeypatch.setattr(
        ModelEmbeddings,
        "embed_documents",
        lambda *args: pytest.fail("deleted post called embedding"),
    )
    poll_once()
    with connection() as conn:
        row = conn.execute("SELECT 1 FROM post_embeddings WHERE post_id=1").fetchone()
    assert row is None


def test_recommend_request_is_deduplicated_until_claimed(infra: None) -> None:
    first = enqueue(READER)
    assert enqueue(READER) == first
    event = claim(("recommend.requested",))
    assert event is not None
    assert enqueue(READER) != first


def test_new_generation_fences_old_graph(infra: None) -> None:
    prepare()
    old = start_graph(READER, pause=True)
    new = start_graph(READER)
    current = claim(("recommend.requested",), event_id=old["event_id"])
    assert current is not None
    assert not run_graph(current)["published"]
    assert read_feed(READER)["snapshot_id"] == new["event_id"]


def test_recent_impression_schedules_refresh_and_feed_read_writes_nothing(infra: None) -> None:
    from sns_recommend.worker.scheduler import schedule_active

    index_all()
    result = TestClient(app).get(f"/internal/feeds/{READER}")
    assert result.status_code == 200 and "refresh_event" not in result.json()
    with connection() as conn:
        assert count(conn, "user_events") == 0
    with source_connection() as conn:
        conn.execute(
            "INSERT INTO post_actions(id,user_id,post_id,action) VALUES (%s,%s,1,'impression')",
            (uuid4(), READER),
        )
    sync_events()
    assert schedule_active() == {"scheduled": 1}
    assert schedule_active() == {"scheduled": 0}
    assert run_one()
    assert read_feed(READER)["ready"]


def test_behavior_only_seed_and_cold_start(infra: None) -> None:
    assert seed_actions() == {"actions": 6}
    assert seed_actions() == {"actions": 0}
    sync_events()
    index_all()
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
