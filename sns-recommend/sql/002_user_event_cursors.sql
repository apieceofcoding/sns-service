CREATE TABLE IF NOT EXISTS user_event_cursors (
 name text PRIMARY KEY,
 changed_at timestamptz NOT NULL,
 last_id bigint NOT NULL
);
