"""Case grouping holds a lock per (tenant, entity) while it looks for an open
case and creates one. The lock was per process, so two API replicas could open
duplicate cases for one entity; it now also takes a Redis lock (SET NX PX with
a token, released only by its holder), and falls back to the local lock when
Redis is down."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from services import case_service  # noqa: E402


class FakeRedis:
    def __init__(self, fail=False):
        self.data, self.fail = {}, fail

    async def set(self, key, value, nx=False, px=None):
        if self.fail:
            raise ConnectionError("down")
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    async def eval(self, script, numkeys, key, token):
        if self.data.get(key) == token:
            del self.data[key]
            return 1
        return 0


def test_two_replicas_take_turns():
    shared = FakeRedis()
    order = []

    async def replica(name, locks):
        async with case_service.GroupLock("acme", "host:web-1", redis=shared, local=locks):
            order.append(f"{name} in")
            await asyncio.sleep(0.05)
            order.append(f"{name} out")

    async def run():
        # separate local lock tables: two processes
        await asyncio.gather(replica("a", {}), replica("b", {}))

    asyncio.run(run())
    assert order in (["a in", "a out", "b in", "b out"], ["b in", "b out", "a in", "a out"])
    assert shared.data == {}  # released


def test_only_the_holder_releases():
    shared = FakeRedis()

    async def run():
        lock = case_service.GroupLock("acme", "k", redis=shared, local={})
        async with lock:
            shared.data[lock.key] = "someone-else"  # the lock expired and another replica took it
        assert shared.data[lock.key] == "someone-else"

    asyncio.run(run())


def test_redis_down_falls_back_to_the_local_lock():
    async def run():
        async with case_service.GroupLock("acme", "k", redis=FakeRedis(fail=True), local={}):
            return True

    assert asyncio.run(run()) is True
