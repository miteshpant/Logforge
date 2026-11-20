"""
API Response Caching Utilities

High-performance caching for frequently accessed API endpoints.
Uses Redis for distributed caching with automatic TTL and invalidation.
"""

import asyncio
import hashlib
import json
import functools
from typing import Any, Callable, Optional, Union
from datetime import datetime
import structlog

from events.management.cache.redis_manager import redis_manager

logger = structlog.get_logger(__name__)

# Cache key prefixes for different data types
CACHE_PREFIX_API = "api:cache:"
CACHE_PREFIX_STATS = "api:stats:"
CACHE_PREFIX_CONFIG = "api:config:"

# Default TTL values (in seconds)
TTL_SHORT = 30       # 30 seconds - for rapidly changing data
TTL_MEDIUM = 300     # 5 minutes - for moderately changing data
TTL_LONG = 3600      # 1 hour - for slowly changing data
TTL_CONFIG = 86400   # 24 hours - for configuration data


def cache_key(*args, **kwargs) -> str:
    """
    Generate a unique cache key from function arguments.

    Uses MD5 hash for consistent, collision-resistant keys.
    """
    import data_scope

    key_parts = [str(arg) for arg in args]
    scope = data_scope.current()
    if scope is not None:  # Phase 14: results under a data scope are not shared with other scopes
        key_parts.append("scope=" + ",".join(scope.services))
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(
    prefix: str = CACHE_PREFIX_API,
    ttl: int = TTL_MEDIUM,
    key_builder: Optional[Callable] = None
):
    """
    Decorator for caching async function results in Redis.

    Args:
        prefix: Cache key prefix for namespacing
        ttl: Time to live in seconds
        key_builder: Optional custom key builder function

    Usage:
        @cached(prefix="api:alerts:", ttl=60)
        async def get_alerts(customer_id: str) -> List[dict]:
            return await fetch_alerts_from_db(customer_id)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_suffix = key_builder(*args, **kwargs)
            else:
                cache_suffix = cache_key(*args, **kwargs)

            full_key = f"{prefix}{func.__name__}:{cache_suffix}"

            try:
                # Try to get from cache
                cached_value = await redis_manager.get(full_key)
                if cached_value is not None:
                    logger.debug("Cache HIT", key=full_key)
                    return cached_value

                logger.debug("Cache MISS", key=full_key)

            except Exception as e:
                logger.warning("Cache read failed, executing function", error=str(e))

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                await redis_manager.set(full_key, result, ttl=ttl)
            except Exception as e:
                logger.warning("Cache write failed", error=str(e))

            return result

        # Add cache invalidation helper
        wrapper.invalidate = lambda *args, **kwargs: invalidate_cache(
            prefix, func.__name__, key_builder, *args, **kwargs
        )

        return wrapper
    return decorator


async def invalidate_cache(
    prefix: str,
    func_name: str,
    key_builder: Optional[Callable],
    *args,
    **kwargs
):
    """Invalidate a specific cache entry."""
    if key_builder:
        cache_suffix = key_builder(*args, **kwargs)
    else:
        cache_suffix = cache_key(*args, **kwargs)

    full_key = f"{prefix}{func_name}:{cache_suffix}"

    try:
        await redis_manager.delete(full_key)
        logger.info("Cache invalidated", key=full_key)
    except Exception as e:
        logger.warning("Cache invalidation failed", error=str(e))


async def invalidate_pattern(pattern: str):
    """
    Invalidate all cache entries matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "api:alerts:*")
    """
    try:
        deleted = await redis_manager.flush_pattern(pattern)
        logger.info("Cache pattern invalidated", pattern=pattern, deleted=deleted)
        return deleted
    except Exception as e:
        logger.warning("Cache pattern invalidation failed", error=str(e))
        return 0


class TenantCache:
    """
    Tenant-scoped cache helper for multi-tenant applications.

    Provides easy cache operations scoped to a specific tenant/customer.
    """

    def __init__(self, customer_id: str, prefix: str = CACHE_PREFIX_API):
        self.customer_id = customer_id
        self.prefix = f"{prefix}{customer_id}:"

    async def get(self, key: str, default: Any = None) -> Any:
        """Get cached value for tenant."""
        full_key = f"{self.prefix}{key}"
        return await redis_manager.get(full_key, default)

    async def set(self, key: str, value: Any, ttl: int = TTL_MEDIUM) -> bool:
        """Set cached value for tenant."""
        full_key = f"{self.prefix}{key}"
        return await redis_manager.set(full_key, value, ttl=ttl)

    async def delete(self, key: str) -> int:
        """Delete cached value for tenant."""
        full_key = f"{self.prefix}{key}"
        return await redis_manager.delete(full_key)

    async def invalidate_all(self) -> int:
        """Invalidate all cached data for this tenant."""
        pattern = f"{self.prefix}*"
        return await invalidate_pattern(pattern)


# Pre-built cache decorators for common use cases
def cached_stats(ttl: int = TTL_SHORT):
    """Cache decorator for statistics endpoints (30s default)."""
    return cached(prefix=CACHE_PREFIX_STATS, ttl=ttl)


def cached_config(ttl: int = TTL_CONFIG):
    """Cache decorator for configuration endpoints (24h default)."""
    return cached(prefix=CACHE_PREFIX_CONFIG, ttl=ttl)


def cached_by_customer(ttl: int = TTL_MEDIUM):
    """
    Cache decorator that uses customer_id as the primary cache key.

    Expects customer_id as the first argument to the decorated function.
    """
    def key_builder(customer_id: str, *args, **kwargs) -> str:
        extra_key = cache_key(*args, **kwargs) if args or kwargs else ""
        return f"{customer_id}:{extra_key}" if extra_key else customer_id

    return cached(prefix=CACHE_PREFIX_API, ttl=ttl, key_builder=key_builder)
