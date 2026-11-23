CREATE TABLE IF NOT EXISTS post_actions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 event_id uuid NOT NULL UNIQUE,
 user_id bigint NOT NULL CHECK(user_id>0),
 post_id bigint NOT NULL CHECK(post_id>0),
 action text NOT NULL CHECK(action IN ('impression','click')),
 created_at timestamptz NOT NULL DEFAULT now(),
 recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS post_actions_one_impression
 ON post_actions(user_id,post_id) WHERE action='impression';
CREATE INDEX IF NOT EXISTS post_actions_sync ON post_actions(recorded_at,id);
CREATE INDEX IF NOT EXISTS likes_sync ON likes(modified_at,id);
CREATE INDEX IF NOT EXISTS posts_sync ON posts(modified_at,id);
