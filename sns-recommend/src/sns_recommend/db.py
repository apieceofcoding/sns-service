from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import settings


@contextmanager
def connection():
    """Recommend database: vectors, events, jobs and checkpoints."""
    with psycopg.connect(settings().database_url, row_factory=dict_row) as conn:
        yield conn


@contextmanager
def source_connection():
    """SNS database. Its timestamps carry no zone, so every session reads them as UTC."""
    with psycopg.connect(settings().source_database_url, row_factory=dict_row,
                         options="-c timezone=UTC") as conn:
        yield conn


def initialize():
    root = Path(__file__).resolve().parents[2]
    with source_connection() as conn:
        # Reuse the app schema rather than maintaining a second users/posts definition.
        app_ddl = root.parent / "sns-app/src/main/resources/ddl.sql"
        if app_ddl.is_file():
            ddl = app_ddl.read_text()
            ddl = ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
            ddl = ddl.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
            conn.execute(ddl)
        conn.execute("""CREATE TABLE IF NOT EXISTS user_interests (
            user_id bigint PRIMARY KEY REFERENCES users(id),
            interests text NOT NULL
        )""")
        for path in sorted((root / "sql/source").glob("*.sql")):
            conn.execute(path.read_text())
    with connection() as conn:
        for path in sorted((root / "sql").glob("*.sql")):
            conn.execute(path.read_text())
