"""Per-user rate limiting with Redis: at most N checks per user per minute.

Fixed-window counter:
    key  rl:user:42:29531237   (29531237 = which minute we're in, since 1970)
    INCR it on every request -> 1, 2, 3 ...
    EXPIRE 60 s -> old windows clean themselves up

Why Redis and not a Python dict? There are 3 API replicas (Step 10). A dict would
give each replica its own count, so a user could make 3x the limit. Redis is the
one shared counter all replicas see. INCR is atomic: two simultaneous requests can
never both read "29" and both write "30".

Known trade-off: a user can do 30 at 12:00:59 and 30 more at 12:01:00. A sliding
window fixes that at the cost of more Redis work; fixed window is fine here.
"""
import logging
import time

from redis import Redis
from redis.exceptions import RedisError

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, redis: Redis, limit: int, window_seconds: int = 60):
        self.redis = redis
        self.limit = limit
        self.window = window_seconds

    def hit(self, user_id: int) -> int | None:
        """Count one request. Returns None if allowed, otherwise seconds until allowed again."""
        now = time.time()
        key = f"rl:user:{user_id}:{int(now // self.window)}"
        try:
            # A pipeline sends both commands in ONE network round trip
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window)
            count, _ = pipe.execute()
        except RedisError as exc:
            # Fail open: if Redis is down, let the request through rather than block everyone.
            # (Nginx will have its own per-IP limit in Step 10 as a second line of defence.)
            log.warning("rate limiter unavailable, allowing request: %s", exc)
            return None

        if count > self.limit:
            return max(1, int(self.window - now % self.window))
        return None
