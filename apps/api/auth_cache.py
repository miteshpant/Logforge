"""
Auth hot-path cache for sessions, users and role assignments (ENH-016).

Every authenticated request performed at least three ClickHouse queries:

    services/user_service.py:550  validate_session()  -> get_session()
                                                      -> get_user_by_id()
    authn_authz_middleware.py     get_user_tenant_roles()

ClickHouse is an OLAP engine; point lookups are the workload it is worst at.
Auth latency was therefore added to every single API call and scaled with
traffic, making the datastore the bottleneck for a workload it was never
designed to serve.

Security properties
-------------------
* **Fails closed.** If Redis is unavailable the cache is bypassed and the
  authoritative database lookup runs. It NEVER invents an answer, and it never
  lets a request through unverified -- a cache outage degrades latency, not
  authorization.
* **Short TTLs** (60s default) bound how long a revoked session or a changed
  role can remain effective. Revocation additionally invalidates explicitly.
* **Negative results are not cached.** Caching "no roles" would let a transient
  failure lock a user out for the whole TTL, and it removes any chance for an
  attacker to farm negative lookups.
* Cache keys are hashed, so session tokens never appear in Redis.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_TTL_SECONDS = 60


def _key(namespace: str, *parts: str) -> str:
    """
    Build a cache key from a hash of its parts.

    Session tokens are bearer credentials: anyone reading Redis (or a backup, or
    `KEYS` output) must not obtain something they can replay.
    """
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"authcache:{namespace}:{digest}"


class AuthCache:
    """Short-TTL cache in front of the authentication datastore."""

    def __init__(self, redis_manager=None, ttl_seconds: Optional[int] = None):
        self._redis = redis_manager
        self.ttl = ttl_seconds or int(
            os.getenv("AUTH_CACHE_TTL_SECONDS", DEFAULT_TTL_SECONDS)
        )
        self.enabled = os.getenv("AUTH_CACHE_ENABLED", "true").strip().lower() not in {
            "false", "0", "no"
        }

    async def _client(self):
        if self._redis is None:
            from events.management.cache.redis_manager import get_redis_manager

            self._redis = await get_redis_manager()
        return getattr(self._redis, "client", None) or self._redis

    async def _get(self, key: str) -> Optional[Any]:
        try:
            client = await self._client()
            raw = await client.get(key)
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except Exception as exc:
            # A cache read failure must be invisible to correctness: the caller
            # falls through to the authoritative lookup.
            logger.debug("Auth cache read failed", error=str(exc))
            return None

    async def _set(self, key: str, value: Any) -> None:
        try:
            client = await self._client()
            await client.set(key, json.dumps(value, default=str), ex=self.ttl)
        except Exception as exc:
            logger.debug("Auth cache write failed", error=str(exc))

    async def _delete(self, key: str) -> None:
        try:
            client = await self._client()
            await client.delete(key)
        except Exception as exc:
            logger.warning("Auth cache invalidation failed", error=str(exc))

    # -- roles -----------------------------------------------------------

    async def get_user_tenant_roles(
        self,
        user_id: str,
        tenant_id: str,
        loader: Callable[[], Any],
    ) -> List[Dict[str, Any]]:
        """
        Return a user's roles for a tenant, using the cache when possible.

        `loader` is the authoritative lookup and is always used on a miss.
        An EMPTY result is deliberately not cached: caching "no roles" would let
        one transient database failure lock a user out for the full TTL, and
        "no roles" produces a 403.
        """
        if not self.enabled:
            return await loader()

        key = _key("roles", user_id, tenant_id)

        cached = await self._get(key)
        if cached is not None:
            return cached

        roles = await loader()

        if roles:
            await self._set(key, roles)

        return roles

    async def invalidate_user_roles(self, user_id: str, tenant_id: str) -> None:
        """Invalidate on role grant/revoke so changes take effect immediately."""
        await self._delete(_key("roles", user_id, tenant_id))

    # -- sessions --------------------------------------------------------

    async def get_session_user(
        self,
        session_token: str,
        loader: Callable[[], Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Return the cached user for a session token.

        A `None` result (invalid/expired session) is never cached, so a revoked
        token cannot be resurrected from cache and a transient failure cannot
        pin a user out.
        """
        if not self.enabled:
            return await loader()

        key = _key("session", session_token)

        cached = await self._get(key)
        if cached is not None:
            return cached

        user = await loader()

        if user:
            await self._set(key, user)

        return user

    async def invalidate_session(self, session_token: str) -> None:
        """Invalidate on logout/revocation so the token stops working at once."""
        await self._delete(_key("session", session_token))


_auth_cache: Optional[AuthCache] = None


def get_auth_cache() -> AuthCache:
    """Get the shared AuthCache, constructing it on first use."""
    global _auth_cache
    if _auth_cache is None:
        _auth_cache = AuthCache()
    return _auth_cache


def reset_auth_cache() -> None:
    """Reset the cache singleton (tests only)."""
    global _auth_cache
    _auth_cache = None
