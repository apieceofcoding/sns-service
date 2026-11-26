import base64
import json
from uuid import uuid4

from redis import Redis

from . import source
from .config import settings
from .events import excluded_ids

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


def publish(user_id, ids, strategy, created_at, model_version=None, experiment=None, arm=None):
    snapshot_id = uuid4().hex
    generation = int(created_at * 1_000_000)
    payload = {
        "snapshot_id": snapshot_id,
        "ids": ids,
        "strategy": strategy,
        "model_version": model_version,
        "experiment": experiment,
        "arm": arm,
        "generation": generation,
        "created_at": created_at,
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


def read_feed(user_id, limit=20, cursor=None):
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
    ids = data["ids"]
    selected, end = [], min(len(ids), offset + limit * 5)
    window = ids[offset:end]
    excluded = excluded_ids(user_id) | (set(window) - source.alive_ids(window))
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
        "model_version": data["model_version"],
        "experiment": data["experiment"],
        "arm": data["arm"],
        "next_cursor": cursor_encode(user_id, data["snapshot_id"], offset) if more else None,
    }
