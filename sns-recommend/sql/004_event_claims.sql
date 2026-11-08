ALTER TABLE user_events ADD COLUMN IF NOT EXISTS claim_id uuid;
ALTER TABLE user_events ADD COLUMN IF NOT EXISTS locked_until timestamptz;
DROP INDEX IF EXISTS user_events_pending_request;
CREATE UNIQUE INDEX IF NOT EXISTS user_events_waiting_request
 ON user_events(user_id) WHERE action='recommend.requested' AND processed_at IS NULL AND claim_id IS NULL;
