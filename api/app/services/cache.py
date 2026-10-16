"""Verdict cache in Redis.

Key:    verdict:{model_version}:{sha256 of normalized text}
Value:  the verdict as JSON
TTL:    24 h, then Redis deletes it by itself

Putting the model version in the key means a new model automatically stops using old
verdicts (different key), with no "flush the cache" step during a deploy.

FAIL OPEN: if Redis is down or slow, act as if it's a cache miss. The cache makes
things faster; it must never make them fail.
"""
import json
import logging

from redis import Redis
from redis.exceptions import RedisError

log = logging.getLogger(__name__)

# Only what's needed to answer the user. took_ms etc. would be misleading when replayed.
CACHED_FIELDS = ("score", "label", "flags", "model_version", "limited_info", "note")


class VerdictCache:
    def __init__(self, redis: Redis, ttl_seconds: int):
        self.redis = redis
        self.ttl = ttl_seconds

    @staticmethod
    def key(model_version: str, text_hash: str) -> str:
        return f"verdict:{model_version}:{text_hash}"

    def get(self, model_version: str, text_hash: str) -> dict | None:
        try:
            raw = self.redis.get(self.key(model_version, text_hash))
        except RedisError as exc:
            log.warning("cache read failed, continuing without cache: %s", exc)
            return None
        return json.loads(raw) if raw else None

    def set(self, text_hash: str, verdict: dict) -> None:
        value = json.dumps({k: verdict[k] for k in CACHED_FIELDS})
        try:
            self.redis.set(self.key(verdict["model_version"], text_hash), value, ex=self.ttl)
        except RedisError as exc:
            log.warning("cache write failed, continuing without cache: %s", exc)
