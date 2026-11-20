"""The AI rate limit is shared: replicas count in one Redis counter per tenant and
minute, so N replicas can't allow N times the limit. If Redis fails, each process
falls back to counting on its own rather than failing every AI request."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from ai import assistant  # noqa: E402
LimitExceeded = assistant.LimitExceeded


class FakeRedis:
    def __init__(self, fail=False):
        self.values, self.ttls, self.fail = {}, {}, fail

    async def incr(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key, seconds):
        self.ttls[key] = seconds


def test_two_replicas_share_one_limit():
    shared = FakeRedis()
    replica_a, replica_b = assistant.RedisRateCounter(shared), assistant.RedisRateCounter(shared)

    async def run():
        allowed = 0
        for i in range(10):
            counter = replica_a if i % 2 else replica_b
            try:
                await assistant.check_rate(counter, "acme", 5, now=1_000.0)
                allowed += 1
            except LimitExceeded:
                pass
        return allowed

    assert asyncio.run(run()) == 5
    assert all(ttl >= 60 for ttl in shared.ttls.values())


def test_the_window_moves_on_each_minute():
    counter = assistant.RedisRateCounter(FakeRedis())

    async def run():
        for _ in range(5):
            await assistant.check_rate(counter, "acme", 5, now=60.0)
        with pytest.raises(LimitExceeded):
            await assistant.check_rate(counter, "acme", 5, now=61.0)
        await assistant.check_rate(counter, "acme", 5, now=125.0)  # next minute
        await assistant.check_rate(counter, "other", 5, now=61.0)  # tenants don't share

    asyncio.run(run())


def test_redis_failure_falls_back_to_counting_in_process():
    counter = assistant.RedisRateCounter(FakeRedis(fail=True))

    async def run():
        for _ in range(3):
            await assistant.check_rate(counter, "acme", 3, now=10.0)
        with pytest.raises(LimitExceeded):
            await assistant.check_rate(counter, "acme", 3, now=10.5)

    asyncio.run(run())
