from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from sns_recommend.core.config import settings
from sns_recommend.data.seed import seed
from sns_recommend.storage.feeds import redis_client
from sns_recommend.storage.postgres import initialize


@pytest.fixture
def infra(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 for isolated local database tests")
    original = settings()
    name = "rec_test_" + uuid4().hex
    # One throwaway database on each server: SNS originals and recommendation data.
    servers = {
        "SOURCE_DATABASE_URL": original.source_database_url,
        "DATABASE_URL": original.database_url,
    }
    admins = [make_conninfo(url, dbname="postgres") for url in servers.values()]
    for admin in admins:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    for variable, url in servers.items():
        monkeypatch.setenv(variable, make_conninfo(url, dbname=name))
    monkeypatch.setenv("REDIS_URL", original.redis_url.rsplit("/", 1)[0] + "/15")
    monkeypatch.setenv("MODEL_MODE", "fixture")
    settings.cache_clear()
    r = redis_client()
    try:
        initialize()
        keys = list(r.scan_iter("recommend:*"))
        if keys:
            r.delete(*keys)
        seed()
        yield
    finally:
        try:
            keys = list(r.scan_iter("recommend:*"))
            if keys:
                r.delete(*keys)
        finally:
            settings.cache_clear()
            for admin in admins:
                with psycopg.connect(admin, autocommit=True) as conn:
                    conn.execute(
                        sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
                    )


def pytest_configure() -> None:
    os.environ.setdefault("MODEL_MODE", "fixture")
