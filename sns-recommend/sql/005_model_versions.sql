CREATE TABLE IF NOT EXISTS model_versions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 status text NOT NULL CHECK(status IN ('candidate','active','retired','rejected')),
 path text NOT NULL,
 embedding_model text NOT NULL,
 trained_until timestamptz NOT NULL,
 sessions int NOT NULL,
 metrics jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 activated_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS model_versions_one_active ON model_versions((true)) WHERE status='active';
