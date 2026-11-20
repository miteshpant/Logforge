"""
Background schedulers (saved searches, scheduled reports, ticket sync,
playbook dispatch) run in every API process. A Redis lease per tick lets one
replica do each tick's work; without Redis every process runs it, as before.
"""

import asyncio

import pytest

import scheduler_lease


class FakeRedis:
    def __init__(self):
        self.keys = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys[key] = (value, ex)
        return True


def test_one_replica_gets_each_tick(monkeypatch):
    redis = FakeRedis()

    async def client():
        return redis

    monkeypatch.setattr(scheduler_lease, "_client", client)
    first = asyncio.run(scheduler_lease.acquire("saved-searches", 30))
    second = asyncio.run(scheduler_lease.acquire("saved-searches", 30))
    other = asyncio.run(scheduler_lease.acquire("reports", 600))
    assert (first, second, other) == (True, False, True)
    # the lease ends just before the next tick, so the next tick can be taken
    assert redis.keys["logforge:lease:saved-searches"][1] == 29


@pytest.mark.parametrize("failure", ["none", "error"])
def test_without_redis_every_process_runs(monkeypatch, failure):
    async def client():
        if failure == "error":
            raise ConnectionError("redis down")
        return None

    monkeypatch.setattr(scheduler_lease, "_client", client)
    assert asyncio.run(scheduler_lease.acquire("saved-searches", 30)) is True
