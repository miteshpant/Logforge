"""
Global request limits: body size caps and per-tenant rate limiting (ENH-012).

Two gaps this closes:

* **No body size cap.** `/v1/ingest/logs/bulk` accepts an unbounded
  `Dict[str, Any]`, and several ingest endpoints call `await request.body()`,
  which buffers the entire payload in memory. A single client could exhaust
  memory with one request.
* **No rate limiting.** The only limiter in the codebase was per-process and
  SSE-specific (`routers/streaming_api.py`), so nothing bounded API call rate
  or provided per-tenant fairness. One noisy tenant could saturate ingest for
  everyone.

Design notes
------------
* The size check reads `Content-Length` and rejects with **413** before the body
  is read, so an oversized payload is never buffered.
* Rate limiting uses a fixed-window counter in Redis keyed by tenant, so limits
  hold across replicas. Fixed windows allow a burst at a boundary; that is an
  accepted trade for O(1) cost on every request. A sliding window is the
  refinement if boundary bursts become a problem.
* Rate limiting **fails open** when Redis is unavailable, which is the opposite
  of the login throttle (ENH-013). The reasoning differs: losing login
  throttling reopens password guessing (a security control), whereas losing
  API rate limiting degrades fairness (an availability control). Making the
  whole API unavailable because Redis blipped would cause the outage we are
  trying to prevent. The degraded state is logged.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# 32 MiB default. Large enough for realistic bulk ingest batches, small enough
# that a handful of concurrent requests cannot exhaust a container's memory.
DEFAULT_MAX_BODY_BYTES = 32 * 1024 * 1024

# Generous default so normal dashboard/query traffic is unaffected; the point is
# to bound abuse, not to shape ordinary use.
DEFAULT_REQUESTS_PER_MINUTE = 6000


@dataclass(frozen=True)
class RequestLimitPolicy:
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE

    @classmethod
    def from_env(cls) -> "RequestLimitPolicy":
        return cls(
            max_body_bytes=int(
                os.getenv("LOGFORGE_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)
            ),
            requests_per_minute=int(
                os.getenv("LOGFORGE_RATE_LIMIT_PER_MINUTE", DEFAULT_REQUESTS_PER_MINUTE)
            ),
        )


class RateLimiter:
    """Fixed-window per-tenant request counter backed by Redis."""

    def __init__(self, redis_manager=None, policy: Optional[RequestLimitPolicy] = None):
        self._redis = redis_manager
        self.policy = policy or RequestLimitPolicy.from_env()

    async def _client(self):
        if self._redis is None:
            from events.management.cache.redis_manager import get_redis_manager

            self._redis = await get_redis_manager()
        return getattr(self._redis, "client", None) or self._redis

    async def check(self, tenant_id: str) -> tuple[bool, int]:
        """
        Consume one unit of the tenant's budget.

        Returns:
            (allowed, retry_after_seconds)

        Fails OPEN on store errors -- see the module docstring for why this
        differs from the login throttle.
        """
        window = int(time.time() // 60)
        key = f"ratelimit:{tenant_id}:{window}"

        try:
            client = await self._client()
            count = int(await client.incr(key))
            if count == 1:
                # Expire slightly after the window so a boundary request cannot
                # resurrect a stale counter.
                await client.expire(key, 120)

            if count > self.policy.requests_per_minute:
                # Seconds remaining in the current minute.
                return False, 60 - int(time.time() % 60)

            return True, 0

        except Exception as exc:
            logger.warning(
                "Rate limit store unavailable; allowing request "
                "(availability preferred over fairness)",
                error=str(exc),
            )
            return True, 0


class StreamRateLimiter:
    """
    Distributed per-customer event rate limiter for SSE streams (ENH-026).

    `routers/streaming_api.py` kept a per-INSTANCE dict keyed by minute, so:

    * limits were per-process -- running N replicas multiplied the effective
      limit by N, which defeats the purpose of having a limit;
    * counters were lost on restart;
    * the same logic was duplicated in two places in that file.

    Counters now live in Redis. Like the API rate limiter above (and unlike the
    login throttle) this **fails open**: dropping a customer's live event stream
    because Redis blipped is a worse outcome than briefly exceeding a soft
    event-rate cap. The fallback is a bounded local counter so a Redis outage
    degrades to the OLD behaviour rather than to no limit at all.
    """

    def __init__(self, redis_manager=None):
        self._redis = redis_manager
        self._local_counts: Dict[str, int] = {}
        self._local_window: Optional[int] = None

    async def _client(self):
        if self._redis is None:
            from events.management.cache.redis_manager import get_redis_manager

            self._redis = await get_redis_manager()
        return getattr(self._redis, "client", None) or self._redis

    def _local_check(self, customer_id: str, window: int, limit: int) -> bool:
        """Bounded in-process fallback used only when Redis is unavailable."""
        if self._local_window != window:
            # New minute: drop the previous window entirely, so this cannot
            # grow without bound the way the original dict could.
            self._local_window = window
            self._local_counts = {}

        count = self._local_counts.get(customer_id, 0)
        if count >= limit:
            return False

        self._local_counts[customer_id] = count + 1
        return True

    async def allow_event(self, customer_id: str, max_events_per_minute: int) -> bool:
        """Consume one event from the customer's per-minute stream budget."""
        window = int(time.time() // 60)
        key = f"streamlimit:{customer_id}:{window}"

        try:
            client = await self._client()
            count = int(await client.incr(key))
            if count == 1:
                await client.expire(key, 120)
            return count <= max_events_per_minute

        except Exception as exc:
            logger.debug(
                "Stream rate limit store unavailable; using local fallback",
                error=str(exc),
            )
            return self._local_check(customer_id, window, max_events_per_minute)


_stream_limiter: Optional[StreamRateLimiter] = None


def get_stream_rate_limiter() -> StreamRateLimiter:
    """Get the shared SSE stream rate limiter."""
    global _stream_limiter
    if _stream_limiter is None:
        _stream_limiter = StreamRateLimiter()
    return _stream_limiter


def reset_stream_rate_limiter() -> None:
    """Reset the limiter singleton (tests only)."""
    global _stream_limiter
    _stream_limiter = None


class RequestLimitsMiddleware(BaseHTTPMiddleware):
    """Enforces body size caps and per-tenant rate limits (ENH-012)."""

    def __init__(self, app, policy: Optional[RequestLimitPolicy] = None,
                 rate_limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.policy = policy or RequestLimitPolicy.from_env()
        self.rate_limiter = rate_limiter or RateLimiter(policy=self.policy)

        # Endpoints exempt from rate limiting. Health must stay reachable for
        # load balancers even when a tenant is being throttled.
        self.exempt_paths = {
            "/health", "/", "/docs", "/openapi.json", "/redoc",
            # ENH-019: Prometheus scrapes on a fixed interval; throttling
            # the scrape would blind us exactly when load is high.
            "/metrics",
        }

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in self.exempt_paths:
            return await call_next(request)

        # ---- Body size cap -------------------------------------------------
        # Checked from the header BEFORE the body is read, so an oversized
        # payload is rejected without ever being buffered.
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared = int(content_length)
            except (TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid Content-Length header"},
                )

            if declared > self.policy.max_body_bytes:
                logger.warning(
                    "Request rejected: body too large",
                    declared_bytes=declared,
                    limit_bytes=self.policy.max_body_bytes,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "request_entity_too_large",
                        "message": (
                            f"Request body of {declared} bytes exceeds the "
                            f"{self.policy.max_body_bytes} byte limit."
                        ),
                        "max_bytes": self.policy.max_body_bytes,
                    },
                )

        # ---- Per-tenant rate limit ----------------------------------------
        # Keyed on the tenant header. Unauthenticated requests share an
        # "anonymous" bucket; the login path is additionally protected by the
        # dedicated throttle in ENH-013.
        tenant_id = request.headers.get("X-Customer-ID") or "anonymous"

        allowed, retry_after = await self.rate_limiter.check(tenant_id)
        if not allowed:
            logger.warning(
                "Request rejected: rate limit exceeded",
                tenant_id=tenant_id,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please slow down.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)


def setup_request_limits(app, policy: Optional[RequestLimitPolicy] = None):
    """Register the request-limits middleware."""
    app.add_middleware(RequestLimitsMiddleware, policy=policy)
    logger.debug("Request limits middleware configured")
