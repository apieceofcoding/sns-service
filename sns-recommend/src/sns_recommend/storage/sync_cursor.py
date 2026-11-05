"""Where the event worker stopped reading each SNS table."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sns_recommend.core.types import DatabaseConnection, DatabaseRow

# A slow transaction can commit after newer rows were read, so recent rows are read again.
OVERLAP = timedelta(seconds=60)
START = datetime(1970, 1, 1, tzinfo=UTC)
Position = tuple[datetime, str]


def load_position(conn: DatabaseConnection, name: str, first_id: str = "0") -> Position:
    row = conn.execute(
        "SELECT changed_at,last_id FROM sync_cursors WHERE name=%s", (name,)
    ).fetchone()
    return (row["changed_at"], row["last_id"]) if row else (START, first_id)


def settled_before(source: DatabaseConnection) -> datetime:
    row = source.execute("SELECT now()-%s AS at", (OVERLAP,)).fetchone()
    assert row is not None  # SELECT without FROM always returns a row.
    return row["at"]


def next_position(
    rows: Sequence[DatabaseRow], current: Position, settled: datetime, first_id: str = "0"
) -> Position:
    """Move past rows that can no longer change order. Never skip the overlap window."""
    if rows and rows[-1]["changed_at"] < settled:
        return rows[-1]["changed_at"], rows[-1]["cursor_id"]
    return (settled, first_id) if settled > current[0] else current


def save_position(conn: DatabaseConnection, name: str, position: Position) -> None:
    conn.execute(
        """INSERT INTO sync_cursors(name,changed_at,last_id) VALUES (%s,%s,%s)
        ON CONFLICT(name) DO UPDATE SET changed_at=EXCLUDED.changed_at,last_id=EXCLUDED.last_id""",
        (name, *position),
    )
