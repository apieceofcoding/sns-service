CREATE TABLE IF NOT EXISTS profiles (user_id bigint PRIMARY KEY, generation bigint NOT NULL DEFAULT 0, active_at timestamptz);
