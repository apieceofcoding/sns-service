from __future__ import annotations

from datetime import UTC, datetime, timedelta

OVERLAP = timedelta(seconds=60)
START = datetime(1970, 1, 1, tzinfo=UTC)


def load_position(conn, name):
    row = conn.execute(
        "SELECT changed_at,last_id FROM user_event_cursors WHERE name=%s", (name,)
    ).fetchone()
    return (row["changed_at"], row["last_id"]) if row else (START, 0)


def settled_before(source):
    return source.execute("SELECT now()-%s AS at", (OVERLAP,)).fetchone()["at"]


def next_position(rows, current, settled):
    if rows and rows[-1]["changed_at"] < settled:
        return rows[-1]["changed_at"], rows[-1]["source_id"]
    return (settled, 0) if settled > current[0] else current


def save_position(conn, name, position):
    conn.execute(
        """INSERT INTO user_event_cursors(name,changed_at,last_id) VALUES (%s,%s,%s)
        ON CONFLICT(name) DO UPDATE SET changed_at=EXCLUDED.changed_at,last_id=EXCLUDED.last_id""",
        (name, *position),
    )
