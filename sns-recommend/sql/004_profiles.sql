ALTER TABLE profiles ADD COLUMN IF NOT EXISTS embedding vector;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS embedding_space text;
ALTER TABLE profiles DROP COLUMN IF EXISTS interests_hash;
