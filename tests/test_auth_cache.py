"""
Tests for ENH-016 -- caching the auth hot path.

Every authenticated request ran at least three ClickHouse queries (session
lookup, user lookup, role lookup). ClickHouse is an OLAP engine and point
lookups are its worst workload, so auth latency was added to every API call and
scaled with traffic.

A cache in front of an authorization decision is dangerous if done carelessly,
so these tests concentrate on the security properties rather than the speedup:

* it must FAIL CLOSED (cache errors fall through to the database, never grant),
* it must NOT cache negative results (a blip must not lock a user out, and a
  revoked token must not be resurrectable),
* revocation must invalidate immediately,
* tokens must never be stored in plaintext keys.
"""

import json

import pytest

from auth_cache import AuthCache, _key, reset_auth_cache


class _FakeRedisClient:
    def __init__(self, fail=False):
        self.store = {}
        self.ttls = {}
        self.fail = fail
        self.reads = 0

    def _guard(self):
        if self.fail:
            raise ConnectionError("redis down")

    async def get(self, key):
        self._guard()
        self.reads += 1
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self._guard()
        self.store[key] = value
        self.ttls[key] = ex
        return True

    async def delete(self, key):
        self._guard()
        self.store.pop(key, None)
        return True


class _FakeRedisManager:
    def __init__(self, fail=False):
        self.client = _FakeRedisClient(fail=fail)


@pytest.fixture(autouse=True)
def clean():
    reset_auth_cache()
    yield
    reset_auth_cache()


def _cache(fail=False, ttl=60):
    return AuthCache(redis_manager=_FakeRedisManager(fail=fail), ttl_seconds=ttl)


ROLES = [{"role": "tenant_admin", "tenant_id": "t1"}]


# ---------------------------------------------------------------------------
# Caching behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_call_uses_the_loader():
    cache = _cache()
    calls = []

    async def loader():
        calls.append(1)
        return ROLES

    result = await cache.get_user_tenant_roles("u1", "t1", loader)

    assert result == ROLES
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_second_call_is_served_from_cache():
    cache = _cache()
    calls = []

    async def loader():
        calls.append(1)
        return ROLES

    await cache.get_user_tenant_roles("u1", "t1", loader)
    result = await cache.get_user_tenant_roles("u1", "t1", loader)

    assert result == ROLES
    assert len(calls) == 1, "Second call should not have hit the database"


@pytest.mark.asyncio
async def test_entries_carry_a_ttl():
    """Without a TTL, a stale role assignment would persist indefinitely."""
    cache = _cache(ttl=42)

    async def loader():
        return ROLES

    await cache.get_user_tenant_roles("u1", "t1", loader)

    assert 42 in cache._redis.client.ttls.values()


@pytest.mark.asyncio
async def test_cache_is_scoped_per_user_and_tenant():
    cache = _cache()

    async def loader_a():
        return [{"role": "viewer", "tenant_id": "t1"}]

    async def loader_b():
        return [{"role": "tenant_admin", "tenant_id": "t2"}]

    a = await cache.get_user_tenant_roles("u1", "t1", loader_a)
    b = await cache.get_user_tenant_roles("u1", "t2", loader_b)

    assert a != b, "Roles for different tenants must not share a cache entry"


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_failure_falls_through_to_the_database():
    """A cache outage must degrade latency, never authorization."""
    cache = _cache(fail=True)
    calls = []

    async def loader():
        calls.append(1)
        return ROLES

    result = await cache.get_user_tenant_roles("u1", "t1", loader)

    assert result == ROLES
    assert len(calls) == 1, "Authoritative lookup must still run"


@pytest.mark.asyncio
async def test_cache_never_invents_roles():
    """
    The cache must never return roles the loader did not produce. If it could,
    a cache bug would become a privilege escalation.
    """
    cache = _cache()

    async def empty_loader():
        return []

    result = await cache.get_user_tenant_roles("u1", "t1", empty_loader)
    assert result == []


@pytest.mark.asyncio
async def test_empty_roles_are_not_cached():
    """
    Caching "no roles" would let one transient database failure lock a user out
    for the whole TTL, since no roles means 403.
    """
    cache = _cache()
    calls = []

    async def flaky_loader():
        calls.append(1)
        return [] if len(calls) == 1 else ROLES

    first = await cache.get_user_tenant_roles("u1", "t1", flaky_loader)
    second = await cache.get_user_tenant_roles("u1", "t1", flaky_loader)

    assert first == []
    assert second == ROLES, "A negative result must not be cached"


@pytest.mark.asyncio
async def test_none_session_is_not_cached():
    """A revoked/expired session must not become resurrectable from cache."""
    cache = _cache()
    calls = []

    async def loader():
        calls.append(1)
        return None

    await cache.get_session_user("tok", loader)
    await cache.get_session_user("tok", loader)

    assert len(calls) == 2, "A None session must never be cached"


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_role_invalidation_forces_a_reload():
    cache = _cache()
    calls = []

    async def loader():
        calls.append(1)
        return ROLES

    await cache.get_user_tenant_roles("u1", "t1", loader)
    await cache.invalidate_user_roles("u1", "t1")
    await cache.get_user_tenant_roles("u1", "t1", loader)

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_session_invalidation_forces_a_reload():
    cache = _cache()
    calls = []

    async def loader():
        calls.append(1)
        return {"id": "u1"}

    await cache.get_session_user("tok", loader)
    await cache.invalidate_session("tok")
    await cache.get_session_user("tok", loader)

    assert len(calls) == 2, "A revoked session must not be served from cache"


def test_revoke_session_invalidates_the_cache():
    """
    The wiring that matters: without this, a logged-out token keeps working
    until the TTL expires.
    """
    import inspect

    from services.user_service import UserService

    source = inspect.getsource(UserService.revoke_session)
    assert "invalidate_session" in source, (
        "revoke_session must invalidate the auth cache, or logout is delayed "
        "by the cache TTL."
    )


# ---------------------------------------------------------------------------
# Key privacy
# ---------------------------------------------------------------------------


def test_session_token_is_not_stored_in_the_key():
    """
    A session token is a bearer credential. Anyone reading Redis, a backup, or
    `KEYS` output must not obtain something replayable.
    """
    token = "super-secret-session-token"
    key = _key("session", token)

    assert token not in key
    assert "secret" not in key


def test_keys_are_namespaced():
    assert _key("roles", "u1", "t1").startswith("authcache:roles:")


def test_different_inputs_produce_different_keys():
    assert _key("roles", "u1", "t1") != _key("roles", "u1", "t2")


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_can_be_disabled(monkeypatch):
    """An operator must be able to turn the cache off without a code change."""
    monkeypatch.setenv("AUTH_CACHE_ENABLED", "false")
    cache = AuthCache(redis_manager=_FakeRedisManager())
    calls = []

    async def loader():
        calls.append(1)
        return ROLES

    await cache.get_user_tenant_roles("u1", "t1", loader)
    await cache.get_user_tenant_roles("u1", "t1", loader)

    assert len(calls) == 2, "Disabled cache must always hit the database"
