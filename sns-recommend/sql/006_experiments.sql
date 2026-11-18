CREATE TABLE IF NOT EXISTS experiments (
 name text PRIMARY KEY,
 control_model bigint,
 treatment_model bigint,
 treatment_spread boolean NOT NULL DEFAULT true,
 min_impressions integer NOT NULL,
 started_at timestamptz NOT NULL DEFAULT now(),
 stopped_at timestamptz,
 decision text
);
CREATE UNIQUE INDEX IF NOT EXISTS experiments_one_running ON experiments((true))
 WHERE stopped_at IS NULL;
