ALTER TABLE posts ADD COLUMN IF NOT EXISTS content_version bigint NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS post_actions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 event_id uuid NOT NULL UNIQUE,
 user_id bigint NOT NULL CHECK(user_id>0),
 post_id bigint NOT NULL CHECK(post_id>0),
 action text NOT NULL CHECK(action IN ('impression','click')),
 -- created_at: when the user saw or clicked. recorded_at: when the row reached the database.
 created_at timestamptz NOT NULL DEFAULT now(),
 recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS post_actions_one_impression
 ON post_actions(user_id,post_id) WHERE action='impression';
CREATE OR REPLACE FUNCTION recommend_post_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.content IS DISTINCT FROM OLD.content OR NEW.deleted_at IS DISTINCT FROM OLD.deleted_at THEN
  NEW.content_version := OLD.content_version+1;
 ELSE
  NEW.content_version := OLD.content_version;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS recommend_version ON posts;
CREATE TRIGGER recommend_version BEFORE UPDATE ON posts FOR EACH ROW EXECUTE FUNCTION recommend_post_version();
DROP TRIGGER IF EXISTS recommend_insert ON posts;
DROP TRIGGER IF EXISTS recommend_update ON posts;
DROP FUNCTION IF EXISTS recommend_post_event();
CREATE INDEX IF NOT EXISTS likes_sync ON likes(modified_at,id);
CREATE INDEX IF NOT EXISTS posts_sync ON posts(modified_at,id);
CREATE INDEX IF NOT EXISTS posts_action_sync ON posts(modified_at,id)
 WHERE parent_id IS NOT NULL OR repost_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS post_actions_sync ON post_actions(recorded_at,id);
