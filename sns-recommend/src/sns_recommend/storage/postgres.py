from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources.abc import Traversable
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from sns_recommend.core.config import settings
from sns_recommend.core.resources import resource_directory
from sns_recommend.core.types import DatabaseConnection


@contextmanager
def connection() -> Iterator[DatabaseConnection]:
    """Recommend database: vectors, profiles and checkpoints."""
    with psycopg.connect(settings().database_url, row_factory=dict_row) as conn:
        yield conn


@contextmanager
def source_connection() -> Iterator[DatabaseConnection]:
    """SNS database. Its timestamps carry no zone, so every session reads them as UTC."""
    with psycopg.connect(
        settings().source_database_url, row_factory=dict_row, options="-c timezone=UTC"
    ) as conn:
        yield conn


def apply(conn: DatabaseConnection, directory: Traversable) -> None:
    for path in sorted(directory.iterdir(), key=lambda entry: entry.name):
        if path.name.endswith(".sql"):
            conn.execute(path.read_text())


def initialize() -> None:
    migrations = resource_directory("sql")
    with source_connection() as conn:
        # Reuse the app schema rather than maintaining a second users/posts definition.
        app_ddl = Path(__file__).resolve().parents[4] / "sns-app/src/main/resources/ddl.sql"
        if app_ddl.is_file():
            ddl = app_ddl.read_text()
            ddl = ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
            ddl = ddl.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
            conn.execute(ddl)
        conn.execute("""CREATE TABLE IF NOT EXISTS user_interests (
            user_id bigint PRIMARY KEY REFERENCES users(id),
            interests text NOT NULL
        )""")
        apply(conn, migrations.joinpath("source"))
    with connection() as conn:
        apply(conn, migrations)
    from sns_recommend.storage.event_queue import migrate_legacy

    migrate_legacy()
