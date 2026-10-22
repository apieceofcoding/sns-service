import base64
import hmac
import json
import time
from uuid import uuid4

from redis import Redis

from .config import settings


def redis_client():
    return Redis.from_url(
        settings().redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
    )


def publish(user_id, ids, strategy):
    snapshot_id = uuid4().hex
    payload = {
        "snapshot_id": snapshot_id,
        "ids": ids,
        "strategy": strategy,
        "created_at": time.time(),
        "generation": 0,
    }
    encoded = json.dumps(payload)
    with redis_client().pipeline() as pipe:
        pipe.set(f"recommend:feed:{user_id}:{snapshot_id}", encoded, ex=settings().snapshot_ttl)
        pipe.set(f"recommend:current:{user_id}", encoded, ex=settings().snapshot_ttl)
        pipe.execute()


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


def read_feed(user_id, limit=20, cursor=None):
    r = redis_client()
    if cursor is not None:
        snapshot, offset = cursor_decode(cursor, user_id)
        raw = r.get(f"recommend:feed:{user_id}:{snapshot}")
        if raw is None:
            raise LookupError("snapshot expired; start a new feed session")
    else:
        raw, offset = r.get(f"recommend:current:{user_id}"), 0
    if raw is None:
        return {"ready": False, "post_ids": [], "next_cursor": None}
    data = json.loads(raw)
    ids = data["ids"]
    selected = ids[offset : offset + limit]
    offset += len(selected)
    return {
        "ready": True,
        "post_ids": selected,
        "snapshot_id": data["snapshot_id"],
        "strategy": data["strategy"],
        "created_at": data["created_at"],
        "next_cursor": cursor_encode(user_id, data["snapshot_id"], offset)
        if offset < len(ids)
        else None,
    }
