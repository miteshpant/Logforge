"""
Tests for ENH-012 -- request body caps and per-tenant rate limiting.

Two gaps:

* No body size cap anywhere. `/v1/ingest/logs/bulk` takes an unbounded
  `Dict[str, Any]`, and several ingest endpoints `await request.body()`, which
  buffers the whole payload. One client could exhaust memory with one request.
* No API rate limiting. The only limiter was per-process and SSE-specific, so
  nothing bounded call rate or gave tenants a fair share.

These use Starlette's TestClient against a minimal app, so no database, Redis
or network is required.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from request_limits import (
    RateLimiter,
    RequestLimitPolicy,
    RequestLimitsMiddleware,
)


class _FakeRedisClient:
    def __init__(self, fail=False):
        self.counts = {}
        self.expiries = {}
        self.fail = fail

    async def incr(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, seconds):
        if self.fail:
            raise ConnectionError("redis down")
        self.expiries[key] = seconds
        return True


class _FakeRedisManager:
    def __init__(self, fail=False):
        self.client = _FakeRedisClient(fail=fail)


def _build_app(policy=None, redis_fail=False):
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/v1/ingest/logs")
    async def ingest():
        return {"status": "accepted"}

    policy = policy or RequestLimitPolicy(
        max_body_bytes=1000, requests_per_minute=1000
    )
    limiter = RateLimiter(
        redis_manager=_FakeRedisManager(fail=redis_fail), policy=policy
    )
    app.add_middleware(
        RequestLimitsMiddleware, policy=policy, rate_limiter=limiter
    )
    return app


# ---------------------------------------------------------------------------
# Body size cap
# ---------------------------------------------------------------------------


def test_oversized_body_is_rejected_with_413():
    client = TestClient(_build_app())

    response = client.post("/v1/ingest/logs", content=b"x" * 5000)

    assert response.status_code == 413
    assert response.json()["error"] == "request_entity_too_large"


def test_body_within_limit_is_accepted():
    client = TestClient(_build_app())

    response = client.post("/v1/ingest/logs", content=b"x" * 100)

    assert response.status_code == 200


def test_413_response_states_the_limit():
    """An operator or client author must be able to see what the cap is."""
    client = TestClient(_build_app())

    body = client.post("/v1/ingest/logs", content=b"x" * 5000).json()

    assert body["max_bytes"] == 1000


def test_malformed_content_length_is_a_client_error():
    client = TestClient(_build_app())

    response = client.post(
        "/v1/ingest/logs",
        content=b"abc",
        headers={"content-length": "not-a-number"},
    )

    # Starlette may reject a malformed length itself; either way it must not be
    # a 5xx and must not reach the handler.
    assert response.status_code in (400, 422)


def test_body_limit_is_configurable():
    policy = RequestLimitPolicy(max_body_bytes=10, requests_per_minute=1000)
    client = TestClient(_build_app(policy=policy))

    assert client.post("/v1/ingest/logs", content=b"x" * 50).status_code == 413


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def test_requests_within_budget_are_allowed():
    policy = RequestLimitPolicy(max_body_bytes=10_000, requests_per_minute=5)
    client = TestClient(_build_app(policy=policy))

    for _ in range(5):
        response = client.post(
            "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "t1"}
        )
        assert response.status_code == 200


def test_exceeding_budget_returns_429():
    policy = RequestLimitPolicy(max_body_bytes=10_000, requests_per_minute=3)
    client = TestClient(_build_app(policy=policy))

    for _ in range(3):
        client.post(
            "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "t1"}
        )

    response = client.post(
        "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "t1"}
    )

    assert response.status_code == 429
    assert response.json()["error"] == "rate_limit_exceeded"


def test_429_includes_retry_after_header():
    policy = RequestLimitPolicy(max_body_bytes=10_000, requests_per_minute=1)
    client = TestClient(_build_app(policy=policy))

    client.post("/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "t1"})
    response = client.post(
        "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "t1"}
    )

    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_budgets_are_per_tenant():
    """One noisy tenant must not consume another tenant's budget."""
    policy = RequestLimitPolicy(max_body_bytes=10_000, requests_per_minute=2)
    client = TestClient(_build_app(policy=policy))

    for _ in range(2):
        client.post(
            "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "noisy"}
        )

    assert client.post(
        "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "noisy"}
    ).status_code == 429

    assert client.post(
        "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "quiet"}
    ).status_code == 200


def test_health_is_exempt_from_rate_limiting():
    """
    Load balancers poll /health. Throttling it would take the service out of
    rotation exactly when it is under load.
    """
    policy = RequestLimitPolicy(max_body_bytes=10_000, requests_per_minute=1)
    client = TestClient(_build_app(policy=policy))

    for _ in range(5):
        assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# Store failure -- fail OPEN here, unlike the login throttle
# ---------------------------------------------------------------------------


def test_rate_limiter_fails_open_when_store_unavailable():
    """
    Deliberately different from ENH-013's login throttle. Losing login
    throttling reopens password guessing (a security control); losing API rate
    limiting only degrades fairness (an availability control). Refusing all
    traffic because Redis blipped would cause the very outage we are preventing.
    """
    policy = RequestLimitPolicy(max_body_bytes=10_000, requests_per_minute=1)
    client = TestClient(_build_app(policy=policy, redis_fail=True))

    for _ in range(5):
        response = client.post(
            "/v1/ingest/logs", content=b"x", headers={"X-Customer-ID": "t1"}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_counter_gets_an_expiry():
    """Without a TTL, counters would accumulate in Redis forever."""
    limiter = RateLimiter(
        redis_manager=_FakeRedisManager(),
        policy=RequestLimitPolicy(requests_per_minute=10),
    )

    await limiter.check("t1")

    assert limiter._redis.client.expiries, "Counter key was created without a TTL"


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_middleware_runs_before_authentication():
    """
    Starlette applies middleware in reverse registration order, so the limits
    middleware must be registered AFTER the auth middleware to run BEFORE it.
    Otherwise an oversized request pays for JWT validation and its database
    lookups before being rejected.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "apps" / "api" / "main.py"
    ).read_text(encoding="utf-8")

    auth_pos = source.index("setup_unified_auth_middleware(app)")
    limits_pos = source.index("setup_request_limits(app)")

    assert auth_pos < limits_pos, (
        "Request limits must be registered after auth so that it executes "
        "before auth (Starlette reverses registration order)."
    )
