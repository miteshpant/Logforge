"""
Regression tests: the Redis-backed security controls must actually reach Redis.

request_limits.RateLimiter, auth_cache.AuthCache and login_throttle.LoginThrottle
resolve their client with ``getattr(manager, "client", None) or manager``.
RedisManager had no public ``client`` (only ``_client``), so they always got the
manager wrapper, which had no ``incr`` and whose ``set`` took ``ttl=`` not
``ex=``. Every call raised and was swallowed, so in the live QA run:

* 12 wrong passwords in a row all returned 401 -- the 5-per-account login
  brute-force throttle never tripped ("Failed to record login failure");
* per-tenant rate limiting failed open on every request;
* the auth cache never stored anything.

These drive the real classes against a real RedisManager whose connection is an
in-memory fake, through both resolution paths.
"""

import pytest

from events.management.cache.redis_manager import RedisManager


class FakeRedis:
    """Just enough of redis.asyncio.Redis for these callers."""

    def __init__(self):
        self.store = {}
        self.ttls = {}

    async def incr(self, key, amount=1):
        self.store[key] = int(self.store.get(key, 0)) + amount
        return self.store[key]

    async def expire(self, key, ttl):
        self.ttls[key] = ttl
        return True

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        if ex:
            self.ttls[key] = ex
        return True

    async def setex(self, key, ttl, value):
        return await self.set(key, value, ex=ttl)

    async def delete(self, *keys):
        return sum(1 for k in keys if self.store.pop(k, None) is not None)


def _connected_manager():
    mgr = RedisManager()
    mgr._client = FakeRedis()
    mgr._connected = True
    return mgr


def test_client_property_exposes_raw_client_only_when_connected():
    mgr = RedisManager()
    assert mgr.client is None
    mgr._client, mgr._connected = FakeRedis(), True
    assert mgr.client is mgr._client


@pytest.mark.asyncio
async def test_manager_wrapper_supports_incr_and_set_ex():
    mgr = _connected_manager()
    assert await mgr.incr("k") == 1
    assert await mgr.incr("k") == 2
    assert await mgr.set("s", "v", ex=30) is True
    assert mgr._client.ttls["s"] == 30


@pytest.mark.asyncio
async def test_login_throttle_locks_account_after_max_failures():
    from login_throttle import LoginThrottle, ThrottlePolicy

    throttle = LoginThrottle(
        redis_manager=_connected_manager(),
        policy=ThrottlePolicy(max_attempts_per_account=5, max_attempts_per_ip=100),
    )
    for _ in range(5):
        assert (await throttle.check("dana@acme.example", "10.0.0.1")).allowed
        await throttle.record_failure("dana@acme.example", "10.0.0.1")

    assert not (await throttle.check("dana@acme.example", "10.0.0.1")).allowed


@pytest.mark.asyncio
async def test_rate_limiter_counts_and_rejects_over_budget():
    from request_limits import RateLimiter, RequestLimitPolicy

    limiter = RateLimiter(
        redis_manager=_connected_manager(),
        policy=RequestLimitPolicy(requests_per_minute=3),
    )
    results = [(await limiter.check("tenant-1"))[0] for _ in range(4)]
    assert results == [True, True, True, False]


@pytest.mark.asyncio
async def test_auth_cache_writes_with_ttl():
    from auth_cache import AuthCache

    mgr = _connected_manager()
    cache = AuthCache(redis_manager=mgr, ttl_seconds=45)
    await cache._set("auth:test", {"ok": True})
    assert await cache._get("auth:test") == {"ok": True}
    assert mgr._client.ttls["auth:test"] == 45
