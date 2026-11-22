CREATE TABLE IF NOT EXISTS user_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 user_id bigint NOT NULL CHECK(user_id>0),
 post_id bigint NOT NULL CHECK(post_id>0),
 action text NOT NULL CHECK(action IN ('like','reply','repost','impression','click')),
 occurred_at timestamptz NOT NULL DEFAULT now(),
 source_id bigint,
 removed_at timestamptz,
 UNIQUE(source_id,action)
);
CREATE INDEX IF NOT EXISTS user_events_history ON user_events(user_id,occurred_at DESC);
