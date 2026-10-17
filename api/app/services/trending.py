"""'Trending this week' leaderboard in a Redis SORTED SET.

A sorted set keeps members ordered by a score, always:
    ZINCRBY trending:2026-W42 1 "17"        -> company 17 gets +1
    ZREVRANGE trending:2026-W42 0 9 WITHSCORES   -> top 10, highest first, already sorted

One key per ISO week ("2026-W42"), expiring after 3 weeks, so last week's scams
naturally drop off and old keys clean themselves up.

Redis is a fast VIEW here; PostgreSQL (companies.verified_reports) stays the source of
truth. If Redis is down, callers get None and fall back to the database.
"""
import logging
from datetime import date

from redis import Redis
from redis.exceptions import RedisError

log = logging.getLogger(__name__)
KEEP_SECONDS = 21 * 24 * 60 * 60


def week_key(day: date | None = None) -> str:
    year, week, _ = (day or date.today()).isocalendar()
    return f"trending:{year}-W{week:02d}"


class TrendingBoard:
    def __init__(self, redis: Redis):
        self.redis = redis

    def record(self, company_id: int) -> None:
        key = week_key()
        try:
            pipe = self.redis.pipeline()
            pipe.zincrby(key, 1, str(company_id))
            pipe.expire(key, KEEP_SECONDS)
            pipe.execute()
        except RedisError as exc:
            # The verified count is already safe in Postgres; only the live view misses one
            log.warning("trending update failed: %s", exc)

    def top(self, limit: int) -> list[tuple[int, int]] | None:
        """[(company_id, verified this week), ...] highest first, or None if Redis is down."""
        try:
            rows = self.redis.zrevrange(week_key(), 0, limit - 1, withscores=True)
        except RedisError as exc:
            log.warning("trending read failed, using the database instead: %s", exc)
            return None
        return [(int(member), int(score)) for member, score in rows]
