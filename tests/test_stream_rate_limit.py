"""
Tests for ENH-026 -- distributed SSE stream rate limiting.

`routers/streaming_api.py` held a per-INSTANCE dict keyed by minute, duplicated
in two places. Consequences:

* Limits were per-process, so running N replicas gave each customer N times the
  intended event budget -- which defeats the point of having a limit.
* Counters were lost on restart.
* Two copies of the same logic could drift apart.

Counters now live in Redis via the shared `StreamRateLimiter`.
"""

import ast
import inspect
from pathlib import Path

import pytest

from request_limits import StreamRateLimiter, reset_stream_rate_limiter

STREAMING_API = (
    Path(__file__).resolve().parent.parent
    / "apps" / "api" / "routers" / "streaming_api.py"
)


class _FakeRedisClient:
    def __init__(self, fail=False):
        self.counts = {}
        self.ttls = {}
        self.fail = fail

    async def incr(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, seconds):
        if self.fail:
            raise ConnectionError("redis down")
        self.ttls[key] = seconds
        return True


class _FakeRedisManager:
    def __init__(self, fail=False):
        self.client = _FakeRedisClient(fail=fail)


@pytest.fixture(autouse=True)
def clean():
    reset_stream_rate_limiter()
    yield
    reset_stream_rate_limiter()


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_within_budget_are_allowed():
    limiter = StreamRateLimiter(redis_manager=_FakeRedisManager())

    for _ in range(5):
        assert await limiter.allow_event("t1", 5) is True


@pytest.mark.asyncio
async def test_events_beyond_budget_are_rejected():
    limiter = StreamRateLimiter(redis_manager=_FakeRedisManager())

    for _ in range(3):
        await limiter.allow_event("t1", 3)

    assert await limiter.allow_event("t1", 3) is False


@pytest.mark.asyncio
async def test_budgets_are_per_customer():
    limiter = StreamRateLimiter(redis_manager=_FakeRedisManager())

    for _ in range(2):
        await limiter.allow_event("noisy", 2)

    assert await limiter.allow_event("noisy", 2) is False
    assert await limiter.allow_event("quiet", 2) is True


@pytest.mark.asyncio
async def test_counters_carry_a_ttl():
    """Without a TTL these keys would accumulate in Redis for every minute."""
    limiter = StreamRateLimiter(redis_manager=_FakeRedisManager())
    await limiter.allow_event("t1", 10)

    assert limiter._redis.client.ttls, "Counter created without an expiry"


@pytest.mark.asyncio
async def test_limits_are_shared_across_instances():
    """
    The headline fix: two limiter instances (standing in for two replicas)
    sharing one Redis must share one budget.
    """
    shared = _FakeRedisManager()
    replica_a = StreamRateLimiter(redis_manager=shared)
    replica_b = StreamRateLimiter(redis_manager=shared)

    assert await replica_a.allow_event("t1", 2) is True
    assert await replica_b.allow_event("t1", 2) is True

    assert await replica_a.allow_event("t1", 2) is False, (
        "Each replica is keeping its own count -- the ENH-026 bug."
    )


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_failure_falls_back_to_a_local_counter():
    """
    Dropping a customer's live stream because Redis blipped is worse than
    briefly exceeding a soft cap, so this fails open -- but to the OLD
    per-process behaviour, not to no limit at all.
    """
    limiter = StreamRateLimiter(redis_manager=_FakeRedisManager(fail=True))

    assert await limiter.allow_event("t1", 2) is True
    assert await limiter.allow_event("t1", 2) is True
    assert await limiter.allow_event("t1", 2) is False, (
        "The local fallback must still enforce a limit."
    )


@pytest.mark.asyncio
async def test_local_fallback_does_not_grow_without_bound():
    """
    The original dict pruned old keys lazily. The fallback drops the whole
    previous window instead, so it cannot accumulate.
    """
    limiter = StreamRateLimiter(redis_manager=_FakeRedisManager(fail=True))

    for i in range(100):
        await limiter.allow_event(f"tenant-{i}", 10)

    limiter._local_check("tenant-x", limiter._local_window + 1, 10)

    assert len(limiter._local_counts) == 1, (
        "Stale window entries were not discarded"
    )


# ---------------------------------------------------------------------------
# The old implementation is gone
# ---------------------------------------------------------------------------


def test_per_instance_rate_limiter_state_is_removed():
    source = STREAMING_API.read_text(encoding="utf-8")
    assert "self.rate_limiter" not in source, (
        "Per-instance rate-limit state remains; limits would still be "
        "per-process."
    )


def test_streaming_api_delegates_to_the_shared_limiter():
    source = STREAMING_API.read_text(encoding="utf-8")
    assert "get_stream_rate_limiter" in source


def test_rate_limit_checks_are_awaited():
    """
    The check became async. A non-awaited call would return a coroutine, which
    is always truthy -- silently disabling the limit entirely.
    """
    source = STREAMING_API.read_text(encoding="utf-8")

    assert "await self._check_rate_limit" in source
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("if not self._check_rate_limit"):
            pytest.fail(f"Un-awaited rate limit check: {stripped}")


def test_no_duplicate_limiter_implementations_remain():
    """The logic existed twice in this file and could have drifted."""
    tree = ast.parse(STREAMING_API.read_text(encoding="utf-8"))
    definitions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_check_rate_limit"
    ]

    for node in definitions:
        body = ast.get_source_segment(
            STREAMING_API.read_text(encoding="utf-8"), node
        )
        assert "get_stream_rate_limiter" in body, (
            "A _check_rate_limit implementation still has its own logic."
        )
