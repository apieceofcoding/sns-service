import base64
import hmac
import json
import time
from uuid import uuid4

from redis import Redis

from .config import settings

# Publish only if no newer run has published. A resumed run reuses its snapshot and its TTL.
PUBLISH = """
local existing = redis.call('GET', KEYS[1])
if existing and existing ~= ARGV[1] then return -1 end
local current = redis.call('GET', KEYS[2])
if current and tonumber(cjson.decode(current).generation or 0) > tonumber(ARGV[3]) then return 0 end
local ttl = tonumber(ARGV[2])
if existing then
  ttl = redis.call('TTL', KEYS[1])
  if ttl < 1 then return 0 end
else
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ttl)
end
redis.call('SET', KEYS[2], ARGV[1], 'EX', ttl)
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
    code = redis_client().eval(
        PUBLISH,
        2,
        f"recommend:feed:{user_id}:{snapshot_id}",
        f"recommend:current:{user_id}",
        encoded,
        settings().snapshot_ttl,
        generation,
    )
    if code == -1:
        raise ValueError("snapshotId reused with different content")
    return code == 1


def current_created_at(user_id):
    raw = redis_client().get(f"recommend:current:{user_id}")
    return json.loads(raw)["created_at"] if raw else None


def cursor_encode(user_id, snapshot_id, offset):
    raw = json.dumps([user_id, snapshot_id, offset], separators=(",", ":")).encode()
    signature = hmac.digest(settings().cursor_secret.encode(), raw, "sha256")
    return base64.urlsafe_b64encode(raw + signature).decode()


def cursor_decode(cursor, user_id):
    try:
        blob = base64.urlsafe_b64decode(cursor)
        raw, sig = blob[:-32], blob[-32:]
        expected = hmac.digest(settings().cursor_secret.encode(), raw, "sha256")
        if not hmac.compare_digest(sig, expected):
            raise ValueError()
        owner, snapshot, offset = json.loads(raw)
        if owner != user_id or not isinstance(offset, int) or offset < 0:
            raise ValueError()
        return snapshot, offset
    except Exception as exc:
        raise ValueError("invalid cursor") from exc


def read_feed(user_id, limit=20, cursor=None, excluded=None, alive=None):
    r = redis_client()
    if cursor:
        snapshot, offset = cursor_decode(cursor, user_id)
        raw = r.get(f"recommend:feed:{user_id}:{snapshot}")
        if raw is None:
            raise LookupError("snapshot expired; start a new feed session")
    else:
        raw, offset = r.get(f"recommend:current:{user_id}"), 0
    if raw is None:
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
