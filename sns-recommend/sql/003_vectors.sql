CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS post_embeddings (
 post_id bigint PRIMARY KEY, content_version bigint NOT NULL,
 space text NOT NULL, embedding vector NOT NULL
);
CREATE TABLE IF NOT EXISTS embedding_cache (
 key text PRIMARY KEY, embedding jsonb NOT NULL
);
