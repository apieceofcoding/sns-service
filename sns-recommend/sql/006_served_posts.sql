CREATE TABLE IF NOT EXISTS served_posts (
 user_id bigint NOT NULL,
 post_id bigint NOT NULL,
 strategy text NOT NULL,
 model_version bigint,
 experiment text,
 arm text,
 served_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (user_id, post_id)
);
