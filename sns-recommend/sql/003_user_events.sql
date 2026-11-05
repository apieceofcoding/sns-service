CREATE TABLE IF NOT EXISTS user_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 user_id bigint NOT NULL CHECK(user_id>0),
 post_id bigint CHECK(post_id>0),
 action text NOT NULL CHECK(action IN ('like','reply','repost','impression','click','recommend.requested')),
 occurred_at timestamptz NOT NULL DEFAULT now(),
 source_key text UNIQUE,
 removed_at timestamptz,
 processed_at timestamptz,
 CHECK ((action='recommend.requested') = (post_id IS NULL))
);
CREATE INDEX IF NOT EXISTS user_events_history ON user_events(user_id,occurred_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS user_events_pending_request
 ON user_events(user_id) WHERE action='recommend.requested' AND processed_at IS NULL;
