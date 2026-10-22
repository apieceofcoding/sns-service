DO $$
BEGIN
 IF to_regclass('recommend_outbox') IS NULL
    AND to_regclass('recommendation_outbox') IS NOT NULL THEN
  ALTER TABLE recommendation_outbox RENAME TO recommend_outbox;
 END IF;
END $$;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS content_version bigint NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS recommend_outbox (
 id uuid PRIMARY KEY, event jsonb NOT NULL, delivered_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS recommend_outbox_pending ON recommend_outbox(created_at,id)
 WHERE delivered_at IS NULL;
