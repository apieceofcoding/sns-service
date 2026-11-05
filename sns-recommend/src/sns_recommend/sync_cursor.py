"""Where the event worker stopped reading each SNS table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# A slow transaction can commit after newer rows were read, so recent rows are read again.
OVERLAP = timedelta(seconds=60)
START = datetime(1970, 1, 1, tzinfo=UTC)


def load_position(conn, name, first_id="0"):
    row = conn.execute(
        "SELECT changed_at,last_id FROM sync_cursors WHERE name=%s", (name,)
    ).fetchone()
    return (row["changed_at"], row["last_id"]) if row else (START, first_id)


def settled_before(source):
    return source.execute("SELECT now()-%s AS at", (OVERLAP,)).fetchone()["at"]


def next_position(rows, current, settled, first_id="0"):
    """Move past rows that can no longer change order. Never skip the overlap window."""
    if rows and rows[-1]["changed_at"] < settled:
        return rows[-1]["changed_at"], rows[-1]["cursor_id"]
    return (settled, first_id) if settled > current[0] else current


def save_position(conn, name, position):
    conn.execute(
        """INSERT INTO sync_cursors(name,changed_at,last_id) VALUES (%s,%s,%s)
        ON CONFLICT(name) DO UPDATE SET changed_at=EXCLUDED.changed_at,last_id=EXCLUDED.last_id""",
        (name, *position),
    )
