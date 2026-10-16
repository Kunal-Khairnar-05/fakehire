"""Caching and rate limiting (fake Redis, fake ml-service, real test database)."""
import redis as redis_lib
from sqlalchemy import text

from app.deps import get_rate_limiter, get_redis
from app.main import app
from app.services.rate_limiter import RateLimiter

POSTING = {"title": "Data Entry", "description": "Pay a registration fee of Rs 1999 to confirm your seat today."}


def check(client, auth, posting=POSTING):
    return client.post("/api/v1/check", json=posting, headers=auth)


# ---------- cache ----------

def test_second_identical_check_is_a_cache_hit(client, auth, ml, db):
    first = check(client, auth)
    second = check(client, auth)

    assert first.headers["X-Cache"] == "MISS" and first.json()["cache_hit"] is False
    assert second.headers["X-Cache"] == "HIT" and second.json()["cache_hit"] is True
    assert second.json()["score"] == first.json()["score"]
    assert ml.calls == 1                       # ml-service was asked only once

    with db.connect() as conn:                 # both are still saved in history
        hits = conn.execute(text("SELECT cache_hit FROM checks ORDER BY id")).scalars().all()
    assert hits == [False, True]


def test_cache_is_shared_between_users(client, auth, new_user, ml):
    check(client, auth)
    other = new_user("ravi@example.com")
    assert check(client, other).headers["X-Cache"] == "HIT"
    assert ml.calls == 1


def test_different_text_is_a_miss(client, auth, ml):
    check(client, auth)
    check(client, auth, {**POSTING, "description": POSTING["description"] + " Hurry!"})
    assert ml.calls == 2


def test_new_model_version_does_not_reuse_old_verdicts(client, auth, ml):
    check(client, auth)
    ml.response = {**ml.response, "model_version": "v1.2"}   # a new model was deployed
    assert check(client, auth).headers["X-Cache"] == "MISS"
    assert ml.calls == 2


def test_cached_verdict_expires(client, auth, redis):
    check(client, auth)
    key = next(redis.scan_iter("verdict:*"))
    assert 0 < redis.ttl(key) <= 24 * 60 * 60


def test_cached_verdict_still_served_while_ml_service_is_down(client, auth, ml):
    check(client, auth)
    ml.down = True
    r = check(client, auth)
    assert r.status_code == 200 and r.json()["cache_hit"] is True


# ---------- rate limit ----------

def test_rate_limit_blocks_after_limit(client, auth, rate_limit):
    for _ in range(rate_limit):
        assert check(client, auth).status_code == 200
    blocked = check(client, auth)
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60


def test_rate_limit_is_per_user(client, auth, new_user, rate_limit):
    for _ in range(rate_limit + 1):
        check(client, auth)
    other = new_user("ravi@example.com")
    assert check(client, other).status_code == 200


def test_blocked_request_never_reaches_ml_service(client, auth, ml, rate_limit):
    for _ in range(rate_limit + 3):
        check(client, auth)
    assert ml.calls == 1          # 1 miss, then cache hits, then blocked ones never get that far


# ---------- Redis down: fail open ----------

def test_everything_still_works_when_redis_is_down(client, auth, ml, rate_limit):
    # Point at a port where nothing is listening: every Redis command fails fast
    dead = redis_lib.Redis(port=1, socket_connect_timeout=0.1, socket_timeout=0.1)
    app.dependency_overrides[get_redis] = lambda: dead
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(dead, rate_limit)

    first, second = check(client, auth), check(client, auth)
    assert first.status_code == second.status_code == 200
    assert second.json()["cache_hit"] is False    # no cache, so ml-service is asked every time
    assert ml.calls == 2
    assert client.get("/health").json()["redis"] == "down"
