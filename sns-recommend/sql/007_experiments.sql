CREATE TABLE IF NOT EXISTS experiments (
 name text PRIMARY KEY,
 started_at timestamptz NOT NULL DEFAULT now(),
 stopped_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS experiments_one_running ON experiments((true))
 WHERE stopped_at IS NULL;
