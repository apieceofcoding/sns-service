ALTER TABLE profiles ADD COLUMN IF NOT EXISTS embedding vector;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS embedding_space text;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS interests_hash text;
