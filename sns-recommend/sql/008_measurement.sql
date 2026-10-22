CREATE TABLE IF NOT EXISTS model_calls (
 id uuid PRIMARY KEY, day date NOT NULL, kind text NOT NULL, model text NOT NULL,
 status text NOT NULL DEFAULT 'started', duration_ms double precision,
 input_tokens int, output_tokens int, estimated_usd double precision,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS generation_runs (
 event_id uuid PRIMARY KEY, mode text NOT NULL, duration_ms double precision,
 strategy text, published boolean, updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='generation_runs' AND column_name='job_id') THEN
  ALTER TABLE generation_runs RENAME COLUMN job_id TO event_id;
 END IF;
END $$;
