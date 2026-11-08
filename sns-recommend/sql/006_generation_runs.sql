CREATE TABLE IF NOT EXISTS generation_runs (
 event_id uuid PRIMARY KEY,
 user_id bigint NOT NULL,
 strategy text,
 model_version bigint,
 duration_ms double precision NOT NULL,
 published boolean,
 error text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS generation_runs_recent ON generation_runs(created_at DESC);
