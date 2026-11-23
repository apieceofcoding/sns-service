import base64
import json
import time
from uuid import uuid4

from redis import Redis

from .config import settings

WANTED = "recommend:wanted"
PUBLISH = """
local current = redis.call('GET', KEYS[2])
if current and tonumber(cjson.decode(current).generation) > tonumber(ARGV[3]) then return 0 end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[2])
return 1
"""


def redis_client():
    return Redis.from_url(
        settings().redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
    )


def publish(
    user_id, ids, strategy, generation, snapshot_id=None, created_at=None, model_version=None
):
    snapshot_id = snapshot_id or uuid4().hex
    payload = {
        "snapshot_id": snapshot_id,
        "user_id": user_id,
        "ids": ids,
        "strategy": strategy,
        "model_version": model_version,
        "generation": generation,
        "created_at": created_at or time.time(),
    }
    encoded = json.dumps(payload, sort_keys=True)
    keys = (f"recommend:feed:{user_id}:{snapshot_id}", f"recommend:current:{user_id}")
    return redis_client().eval(PUBLISH, 2, *keys, encoded, settings().snapshot_ttl, generation) == 1


def current_created_at(user_id):
    raw = redis_client().get(f"recommend:current:{user_id}")
    return json.loads(raw)["created_at"] if raw else None


def cursor_encode(user_id, snapshot_id, offset):
    raw = json.dumps([user_id, snapshot_id, offset], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode()


def cursor_decode(cursor, user_id):
    try:
        owner, snapshot, offset = json.loads(base64.urlsafe_b64decode(cursor))
        valid = owner == user_id and isinstance(snapshot, str) and snapshot.isalnum()
        if not valid or type(offset) is not int or offset < 0:
            raise ValueError()
        return snapshot, offset
    except Exception as exc:
        raise ValueError("invalid cursor") from exc


def read_feed(user_id, limit=20, cursor=None, excluded=None, alive=None):
    r = redis_client()
    raw = None
    if cursor:
        snapshot, offset = cursor_decode(cursor, user_id)
        raw = r.get(f"recommend:feed:{user_id}:{snapshot}")
    if raw is None:
        raw, offset = r.get(f"recommend:current:{user_id}"), 0
    if raw is None:
        r.sadd(WANTED, user_id)
        return {"ready": False, "post_ids": [], "next_cursor": None}
    data = json.loads(raw)
    excluded = excluded or set()
    ids = data["ids"]
    selected, end = [], min(len(ids), offset + limit * 5)
    if alive is not None:
        window = ids[offset:end]
        excluded = excluded | (set(window) - alive(window))
    while offset < end and len(selected) < limit:
        post_id = ids[offset]
        offset += 1
        if post_id not in excluded:
            selected.append(post_id)
    more = offset < len(ids)
    return {
        "ready": True,
        "post_ids": selected,
        "snapshot_id": data["snapshot_id"],
        "strategy": data["strategy"],
        "model_version": data.get("model_version"),
        "created_at": data["created_at"],
        "stale": time.time() - data["created_at"] >= settings().refresh_seconds,
        "next_cursor": cursor_encode(user_id, data["snapshot_id"], offset) if more else None,
    }
