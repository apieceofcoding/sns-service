ALTER TABLE posts ADD COLUMN IF NOT EXISTS content_version bigint NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS recommend_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 action text NOT NULL CHECK(action IN ('post.updated','post.deleted','impression','click','like','not_interested','profile.updated','recommend.requested')),
 user_id bigint CHECK(user_id>0), post_id bigint CHECK(post_id>0), version bigint,
 created_at timestamptz NOT NULL DEFAULT now(),
 claim_id uuid, locked_until timestamptz, processed_at timestamptz,
 CHECK ((action IN ('post.updated','post.deleted') AND post_id IS NOT NULL AND version IS NOT NULL AND version>0)
     OR (action IN ('impression','click','like','not_interested') AND user_id IS NOT NULL AND post_id IS NOT NULL AND version IS NULL)
     OR (action IN ('profile.updated','recommend.requested') AND user_id IS NOT NULL AND version IS NULL)),
 CHECK ((claim_id IS NULL) = (locked_until IS NULL))
);
CREATE INDEX IF NOT EXISTS recommend_events_pending ON recommend_events(created_at,id) WHERE processed_at IS NULL;
CREATE INDEX IF NOT EXISTS recommend_events_history ON recommend_events(user_id,created_at DESC) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS recommend_events_post_version ON recommend_events(post_id,version) WHERE action IN ('post.updated','post.deleted');
CREATE UNIQUE INDEX IF NOT EXISTS recommend_events_pending_request ON recommend_events(user_id) WHERE action='recommend.requested' AND processed_at IS NULL AND claim_id IS NULL;
DO $$
DECLARE old_name text;
BEGIN
 FOREACH old_name IN ARRAY ARRAY['recommend_outbox','recommendation_outbox'] LOOP
  IF to_regclass(old_name) IS NOT NULL THEN
   EXECUTE format('INSERT INTO recommend_events(id,action,user_id,post_id,version,created_at)
    SELECT id,event->>''kind'',(event->>''user_id'')::bigint,(event->>''post_id'')::bigint,
    (event->>''version'')::bigint,created_at FROM %I ON CONFLICT DO NOTHING',old_name);
   EXECUTE format('DROP TABLE %I',old_name);
  END IF;
 END LOOP;
END $$;
CREATE OR REPLACE FUNCTION recommend_post_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.content IS DISTINCT FROM OLD.content OR NEW.deleted_at IS DISTINCT FROM OLD.deleted_at THEN
  NEW.content_version := OLD.content_version+1;
 ELSE
  NEW.content_version := OLD.content_version;
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION recommend_post_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO recommend_events(action,post_id,version)
 VALUES (CASE WHEN NEW.deleted_at IS NOT NULL THEN 'post.deleted' ELSE 'post.updated' END,NEW.id,NEW.content_version)
 ON CONFLICT DO NOTHING;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS recommend_version ON posts;
CREATE TRIGGER recommend_version BEFORE UPDATE ON posts FOR EACH ROW EXECUTE FUNCTION recommend_post_version();
DROP TRIGGER IF EXISTS recommend_insert ON posts;
CREATE TRIGGER recommend_insert AFTER INSERT ON posts FOR EACH ROW EXECUTE FUNCTION recommend_post_event();
DROP TRIGGER IF EXISTS recommend_update ON posts;
CREATE TRIGGER recommend_update AFTER UPDATE ON posts FOR EACH ROW
 WHEN (NEW.content_version IS DISTINCT FROM OLD.content_version) EXECUTE FUNCTION recommend_post_event();

CREATE OR REPLACE FUNCTION recommend_interest_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO recommend_events(action,user_id) VALUES ('profile.updated',NEW.user_id);
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS recommend_interest_insert ON user_interests;
CREATE TRIGGER recommend_interest_insert AFTER INSERT ON user_interests FOR EACH ROW EXECUTE FUNCTION recommend_interest_event();
DROP TRIGGER IF EXISTS recommend_interest_update ON user_interests;
CREATE TRIGGER recommend_interest_update AFTER UPDATE ON user_interests FOR EACH ROW
 WHEN (NEW.interests IS DISTINCT FROM OLD.interests) EXECUTE FUNCTION recommend_interest_event();
