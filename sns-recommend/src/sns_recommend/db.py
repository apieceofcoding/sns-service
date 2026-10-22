from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import settings


@contextmanager
def source_connection():
    with psycopg.connect(settings().source_database_url, row_factory=dict_row) as conn:
        yield conn


def initialize():
    root = Path(__file__).resolve().parents[2]
    # Reuse the app schema rather than maintaining a second users/posts definition.
    ddl = (root.parent / "sns-app/src/main/resources/ddl.sql").read_text()
    ddl = ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
    ddl = ddl.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
    with source_connection() as conn:
        conn.execute(ddl)
        conn.execute("DROP TABLE IF EXISTS user_interests")
        conn.execute("DROP TRIGGER IF EXISTS recommend_interest_insert ON users")
        conn.execute("DROP TRIGGER IF EXISTS recommend_interest_update ON users")
        conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS interests")
