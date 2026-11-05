CREATE TABLE IF NOT EXISTS sync_cursors (
 name text PRIMARY KEY,
 changed_at timestamptz NOT NULL,
 last_id text NOT NULL
);
