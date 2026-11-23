from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from .config import settings


@contextmanager
def connection():
    with psycopg.connect(settings().database_url, row_factory=dict_row) as conn:
        yield conn


@contextmanager
def source_connection():
    with psycopg.connect(
        settings().source_database_url, row_factory=dict_row, options="-c timezone=UTC"
    ) as conn:
        yield conn


def initialize():
    root = Path(__file__).resolve().parents[2]
    with source_connection() as conn:
        app_ddl = root.parent / "sns-app/src/main/resources/ddl.sql"
        if app_ddl.is_file():
            ddl = app_ddl.read_text()
            ddl = ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
            ddl = ddl.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
            conn.execute(ddl)
        for path in sorted((root / "sql/source").glob("*.sql")):
            conn.execute(path.read_text())
    with connection() as conn:
        for path in sorted((root / "sql").glob("*.sql")):
            conn.execute(path.read_text())


def clear_tables(conn):
    tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
    names = sql.SQL(",").join(sql.Identifier(t["tablename"]) for t in tables)
    conn.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY").format(names))
