CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS post_embeddings (
 post_id bigint PRIMARY KEY, content_version bigint NOT NULL,
 model text NOT NULL, embedding vector NOT NULL
);
